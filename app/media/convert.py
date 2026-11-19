"""Turn any upload into something a pipeline can use, or a clear UnsupportedFile message.

images -> JPEG (longest side <= image.max_side, EXIF rotation applied, first GIF frame)
audio  -> 16 kHz mono WAV
video  -> H.264 MP4, at most 1280 wide and 720 high, first server.video_max_seconds only
docs   -> text per page (PDF via PyMuPDF; docx / txt / md as one page)
data   -> copied as-is under its original name (csv / json / py)
.webm is audio or video depending on what ffprobe finds inside.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path, PurePath

from app.contracts import MESSAGES, Attachment, AttachmentKind, UnsupportedFile
from app.settings import Profile

IMAGE_EXT = frozenset({".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".bmp", ".gif"})
AUDIO_EXT = frozenset({".wav", ".mp3", ".m4a", ".aac", ".webm", ".ogg", ".flac"})
VIDEO_EXT = frozenset({".mp4", ".mov", ".m4v", ".webm", ".avi"})
DOC_EXT = frozenset({".pdf", ".docx", ".txt", ".md"})
DATA_EXT = frozenset({".csv", ".json", ".py"})

FFMPEG_TIMEOUT_S = 120


def _unsupported(ext: str) -> UnsupportedFile:
    if not ext:
        return UnsupportedFile(MESSAGES["unsupported_ext"].format(ext="").replace(" . ", " these "))
    return UnsupportedFile(MESSAGES["unsupported_ext"].format(ext=ext.lstrip(".")))


def _out_path(workdir: Path, stem: str, suffix: str, src: Path) -> Path:
    """workdir/<stem><suffix>, never the source file itself and never an earlier output."""
    out = workdir / f"{stem}{suffix}"
    n = 1
    while out.exists() or out.resolve() == src.resolve():
        out = workdir / f"{stem}_{n}{suffix}"
        n += 1
    return out


def _ffmpeg(args: list[str], ext: str) -> None:
    try:
        p = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], capture_output=True,
                           check=False, timeout=FFMPEG_TIMEOUT_S)
    except subprocess.TimeoutExpired as e:
        raise _unsupported(ext) from e
    if p.returncode != 0:
        raise _unsupported(ext)


def probe(path: Path) -> dict:
    """{"has_video": bool, "has_audio": bool, "duration": float} from ffprobe."""
    try:
        p = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                            "stream=codec_type,disposition:format=duration", "-of", "json", str(path)],
                           capture_output=True, text=True, check=False, timeout=30)
        data = json.loads(p.stdout or "{}") if p.returncode == 0 else None
    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        data = None
    if not data:
        raise _unsupported(PurePath(path).suffix.lower())
    streams = data.get("streams", [])
    # Cover art in audio files shows up as a video stream with attached_pic=1; it isn't video.
    has_video = any(s.get("codec_type") == "video"
                    and not s.get("disposition", {}).get("attached_pic") for s in streams)
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    try:
        duration = float(data.get("format", {}).get("duration", 0.0))
    except (TypeError, ValueError):
        duration = 0.0
    return {"has_video": has_video, "has_audio": has_audio, "duration": duration}


def read_document(path: Path) -> list[str]:
    """PDF -> one string per page. docx / txt / md -> [whole text]."""
    ext = path.suffix.lower()
    try:
        if ext == ".pdf":
            import pymupdf

            with pymupdf.open(path) as doc:
                return [page.get_text().strip() for page in doc]
        if ext == ".docx":
            import docx

            d = docx.Document(str(path))
            parts = [p.text for p in d.paragraphs if p.text.strip()]
            for table in d.tables:
                for row in table.rows:
                    parts.append(" | ".join(c.text.strip() for c in row.cells))
            return ["\n".join(parts).strip()]
        return [path.read_text(encoding="utf-8", errors="replace").strip()]
    except Exception as e:
        raise _unsupported(ext) from e


def _image(src: Path, stem: str, ext: str, profile: Profile, workdir: Path) -> Path:
    from PIL import Image, ImageOps, UnidentifiedImageError

    out = _out_path(workdir, stem, ".jpg", src)
    source = src
    if ext in (".heic", ".heif"):  # Pillow can't read HEIC without a plugin; ffmpeg can
        source = _out_path(workdir, stem + "_heic", ".png", src)
        _ffmpeg(["-i", str(src), "-frames:v", "1", str(source)], ext)
    try:
        with Image.open(source) as im:
            im.seek(0)  # first frame of a GIF
            im = ImageOps.exif_transpose(im).convert("RGB")
            side = profile.image.max_side
            if max(im.size) > side:
                im.thumbnail((side, side), Image.Resampling.LANCZOS)
            im.save(out, "JPEG", quality=90)
    except (UnidentifiedImageError, OSError, ValueError) as e:
        out.unlink(missing_ok=True)
        raise _unsupported(ext) from e
    finally:
        if source != src:
            source.unlink(missing_ok=True)
    return out


def _audio(src: Path, stem: str, ext: str, workdir: Path) -> Path:
    out = _out_path(workdir, stem, ".wav", src)
    _ffmpeg(["-i", str(src), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(out)], ext)
    return out


def _video(src: Path, stem: str, ext: str, duration: float, profile: Profile,
           workdir: Path) -> tuple[Path, list[str]]:
    out = _out_path(workdir, stem, ".mp4", src)
    limit = profile.server.video_max_seconds
    _ffmpeg(["-i", str(src), "-t", str(limit),
             "-vf", ("scale=w='min(1280,iw)':h='min(720,ih)':force_original_aspect_ratio=decrease"
                    ":force_divisible_by=2"),
             "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-movflags", "+faststart", str(out)], ext)
    notes = [MESSAGES["video_trimmed"]] if duration > limit + 0.5 else []
    return out, notes


def normalize(path: Path, original_name: str, profile: Profile, workdir: Path) -> Attachment:
    """Convert one upload, named after `original_name`. Bad input raises UnsupportedFile (its
    message is shown verbatim), never another exception."""
    path, workdir = Path(path), Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    name = PurePath(original_name)
    ext, stem = name.suffix.lower(), name.stem
    if ext not in IMAGE_EXT | AUDIO_EXT | VIDEO_EXT | DOC_EXT | DATA_EXT:
        raise _unsupported(ext)
    if not path.is_file() or path.stat().st_size == 0:
        raise UnsupportedFile(MESSAGES["empty_file"])

    def att(p: Path | None, kind: AttachmentKind, **kw) -> Attachment:
        return Attachment(path=p, kind=kind, original_name=original_name, **kw)

    if ext in DATA_EXT:
        out = workdir / name.name
        if out.resolve() != path.resolve():
            shutil.copyfile(path, out)
        return att(out, "data")
    if ext in DOC_EXT:
        src = path
        if path.suffix.lower() != ext:  # parsers pick the format from the suffix
            src = _out_path(workdir, stem, ext, path)
            shutil.copyfile(path, src)
        return att(src, "document", pages=read_document(src))
    if ext in IMAGE_EXT:
        return att(_image(path, stem, ext, profile, workdir), "image")

    info = probe(path)
    if ext in VIDEO_EXT and info["has_video"]:
        out, notes = _video(path, stem, ext, info["duration"], profile, workdir)
        return att(out, "video", notes=notes)
    if ext in AUDIO_EXT and info["has_audio"]:
        return att(_audio(path, stem, ext, workdir), "audio")
    raise _unsupported(ext)
