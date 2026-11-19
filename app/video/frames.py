"""Evenly spaced, timestamped frames from a video, plus the sharpest frames for reading text.

Frames are cached under <cache_dir>/frames/<sha256 of the file>/ with meta.json. A cache hit
needs the same file bytes and the same n, side and sharp, and every frame file still on disk,
so a re-encoded clip with the same name never reuses old frames.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from app.contracts import MESSAGES, UnsupportedFile

SHARP_SAMPLE_FPS = 2.0      # sharpness is measured on frames sampled at 2 fps
SHARP_MIN_GAP_S = 1.0       # sharp frames at least this far apart, when the clip allows it
JPEG_QUALITY = 90


@dataclass
class FrameSet:
    paths: list[Path]          # JPEGs, `side` px on the long side, in time order
    timestamps: list[float]    # seconds, same order
    sharp_paths: list[Path]    # native-resolution sharpest frames (empty unless asked)
    cached: bool


def file_hash(path: Path) -> str:
    """sha256 of the bytes, read in 1 MB chunks."""
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _unreadable(path: Path) -> UnsupportedFile:
    return UnsupportedFile(MESSAGES["unsupported_ext"].format(ext=Path(path).suffix.lstrip(".").lower() or "video"))


def _resize(frame, side: int):
    import cv2

    h, w = frame.shape[:2]
    scale = side / max(h, w)
    if scale == 1:
        return frame
    interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
    return cv2.resize(frame, (max(1, round(w * scale)), max(1, round(h * scale))), interpolation=interp)


def _sharpness(frame) -> float:
    import cv2

    grey = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(grey, cv2.CV_64F).var())


def _load_cache(folder: Path, n: int, side: int, sharp: int) -> FrameSet | None:
    meta_file = folder / "meta.json"
    try:
        meta = json.loads(meta_file.read_text())
    except (OSError, ValueError):
        return None
    if (meta.get("n"), meta.get("side"), meta.get("sharp")) != (n, side, sharp):
        return None
    paths = [folder / p for p in meta["frames"]]
    sharp_paths = [folder / p for p in meta["sharp_frames"]]
    if not all(p.is_file() for p in paths + sharp_paths):
        return None
    return FrameSet(paths, [float(t) for t in meta["timestamps"]], sharp_paths, cached=True)


def extract_frames(path: Path, n: int, side: int, sharp: int, cache_dir: Path) -> FrameSet:
    import cv2

    path = Path(path)
    digest = file_hash(path)
    folder = Path(cache_dir) / "frames" / digest
    hit = _load_cache(folder, n, side, sharp)
    if hit:
        return hit

    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            raise _unreadable(path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if fps <= 0 or total <= 0:
            raise _unreadable(path)
        duration = total / fps

        # Evenly spaced: t_i = duration * (i + 0.5) / n, read as the nearest frame index.
        wanted = sorted({min(total - 1, int(duration * (i + 0.5) / n * fps)) for i in range(n)})
        sample_every = max(1, round(fps / SHARP_SAMPLE_FPS)) if sharp else 0

        frames: dict[int, object] = {}
        scored: list[tuple[float, int, object]] = []
        want = set(wanted)
        last_needed = max(wanted) if not sharp else total - 1
        idx = 0
        while idx <= last_needed:
            need = idx in want or (sample_every and idx % sample_every == 0)
            if not cap.grab():
                break
            if need:
                ok, frame = cap.retrieve()
                if ok:
                    if idx in want:
                        frames[idx] = frame
                    if sample_every and idx % sample_every == 0:
                        scored.append((_sharpness(frame), idx, frame))
            idx += 1
    finally:
        cap.release()

    if not frames:
        raise _unreadable(path)

    if folder.exists():
        shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True, exist_ok=True)

    names, timestamps = [], []
    for k, i in enumerate(sorted(frames)):
        name = f"frame_{k:02d}.jpg"
        cv2.imwrite(str(folder / name), _resize(frames[i], side), [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        names.append(name)
        timestamps.append(round(i / fps, 3))

    sharp_names: list[str] = []
    if sharp:
        chosen: list[tuple[float, int, object]] = []
        min_gap = SHARP_MIN_GAP_S * fps
        for cand in sorted(scored, key=lambda c: c[0], reverse=True):
            if all(abs(cand[1] - c[1]) >= min_gap for c in chosen):
                chosen.append(cand)
            if len(chosen) == sharp:
                break
        taken = {c[1] for c in chosen}
        for cand in sorted(scored, key=lambda c: c[0], reverse=True):  # short clip: relax the gap
            if len(chosen) == sharp:
                break
            if cand[1] not in taken:
                chosen.append(cand)
                taken.add(cand[1])
        for k, (_, i, frame) in enumerate(sorted(chosen, key=lambda c: c[1])):
            name = f"sharp_{k:02d}.jpg"
            cv2.imwrite(str(folder / name), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            sharp_names.append(name)

    (folder / "meta.json").write_text(json.dumps({
        "n": n, "side": side, "sharp": sharp, "timestamps": timestamps,
        "frames": names, "sharp_frames": sharp_names, "fps": fps, "duration": duration,
    }))
    return FrameSet([folder / x for x in names], timestamps, [folder / x for x in sharp_names], cached=False)
