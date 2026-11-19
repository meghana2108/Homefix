"""Tiny media files built at test time. Anyone may import these; only Akshayaa edits this file.

Nothing here comes from the practice pack (hard rule 1).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

FFMPEG_SKIP = "install ffmpeg: brew install ffmpeg"


def need_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip(FFMPEG_SKIP)


def _ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True, timeout=120)


def make_jpeg(path: Path, size=(800, 500), circles: int = 3) -> Path:
    """White image with `circles` red circles in a row."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", size, "white")
    d = ImageDraw.Draw(img)
    r = min(size[1] // 5, size[0] // (3 * max(circles, 1)))
    for i in range(circles):
        cx = (i + 1) * size[0] // (circles + 1)
        d.ellipse([cx - r, size[1] // 2 - r, cx + r, size[1] // 2 + r], fill="red")
    img.save(path, "JPEG", quality=92)
    return path


def make_png(path: Path, size=(3000, 2000)) -> Path:
    from PIL import Image

    Image.new("RGB", size, (30, 120, 200)).save(path, "PNG")
    return path


def make_sine_wav(path: Path, seconds: float = 2.0, hz: int = 1000, sr: int = 44100,
                  channels: int = 1) -> Path:
    import soundfile as sf

    t = np.arange(int(sr * seconds)) / sr
    tone = 0.5 * np.sin(2 * np.pi * hz * t)
    sf.write(path, np.stack([tone] * channels, axis=1) if channels > 1 else tone, sr)
    return path


def make_speech_wav(path: Path, text: str) -> Path:
    """macOS `say` -> 16 kHz mono WAV via ffmpeg. Skips where `say` doesn't exist."""
    if shutil.which("say") is None:
        pytest.skip("macOS `say` not available")
    need_ffmpeg()
    aiff = path.with_suffix(".aiff")
    subprocess.run(["say", "-o", str(aiff), text], check=True, timeout=60)
    _ffmpeg("-i", str(aiff), "-ac", "1", "-ar", "16000", str(path))
    aiff.unlink(missing_ok=True)
    return path


def make_video(path: Path, seconds: float = 4.0, fps: int = 10, size=(640, 360),
               audio: bool = False, color=(255, 255, 255)) -> Path:
    """A square of `color` moving left to right on black. `audio=True` adds a sine track (ffmpeg)."""
    import cv2

    w, h = size
    raw = path.with_name(path.stem + "_raw.mp4") if audio or path.suffix != ".mp4" else path
    out = cv2.VideoWriter(str(raw), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    n = max(int(seconds * fps), 1)
    side = h // 4
    for i in range(n):
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        x = int((w - side) * i / max(n - 1, 1))
        frame[h // 2 - side // 2: h // 2 + side // 2, x: x + side] = color[::-1]  # BGR
        out.write(frame)
    out.release()
    if raw == path:
        return path
    need_ffmpeg()
    if audio:
        _ffmpeg("-i", str(raw), "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
                "-shortest", "-c:v", "copy" if path.suffix == ".mp4" else "libvpx",
                "-c:a", "aac" if path.suffix == ".mp4" else "libopus", str(path))
    else:
        _ffmpeg("-i", str(raw), "-c:v", "libvpx" if path.suffix == ".webm" else "libx264", str(path))
    raw.unlink(missing_ok=True)
    return path


def make_webm_audio_only(path: Path) -> Path:
    need_ffmpeg()
    _ffmpeg("-f", "lavfi", "-i", "sine=frequency=880:duration=2", "-c:a", "libopus", str(path))
    return path


def make_heic(path: Path, size=(1200, 900)) -> Path:
    """A real HEIC (as an iPhone writes) via macOS `sips`. Skips where `sips` doesn't exist."""
    if shutil.which("sips") is None:
        pytest.skip("macOS `sips` not available")
    src = make_jpeg(path.with_suffix(".src.jpg"), size=size)
    subprocess.run(["sips", "-s", "format", "heic", str(src), "--out", str(path)],
                   check=True, capture_output=True, timeout=60)
    src.unlink(missing_ok=True)
    return path


def make_pdf(path: Path, pages: list[str]) -> Path:
    import pymupdf

    doc = pymupdf.open()
    for text in pages:
        doc.new_page().insert_text((72, 72), text)
    doc.save(path)
    doc.close()
    return path


def make_docx(path: Path, paragraphs: list[str]) -> Path:
    import docx

    d = docx.Document()
    for p in paragraphs:
        d.add_paragraph(p)
    d.save(path)
    return path
