"""Video frames: evenly spaced, timestamped, the sharpest frames for reading, cached by content."""

import json
import time

import pytest
from PIL import Image

from app.contracts import UnsupportedFile
from app.video.frames import extract_frames, file_hash
from tests import media_fixtures as mf


@pytest.fixture
def video(tmp_path):
    return mf.make_video(tmp_path / "clip.mp4", seconds=4.0, fps=10, size=(640, 360))


def long_side(p):
    with Image.open(p) as im:
        return max(im.size)


def test_eight_frames(video, tmp_path):
    fs = extract_frames(video, n=8, side=448, sharp=0, cache_dir=tmp_path / "cache")
    assert len(fs.paths) == len(fs.timestamps) == 8
    assert all(0 < t < 4 for t in fs.timestamps)
    assert fs.timestamps == sorted(fs.timestamps) and len(set(fs.timestamps)) == 8
    assert all(long_side(p) == 448 for p in fs.paths)
    assert fs.sharp_paths == [] and fs.cached is False


def test_sixteen_frames_evenly_spaced(video, tmp_path):
    fs = extract_frames(video, n=16, side=448, sharp=0, cache_dir=tmp_path / "cache")
    assert len(fs.paths) == 16
    gaps = [b - a for a, b in zip(fs.timestamps, fs.timestamps[1:])]
    assert max(gaps) - min(gaps) <= 0.11  # one frame at 10 fps


def test_frames_follow_the_motion(video, tmp_path):
    """The square moves left to right: its x position must increase frame by frame."""
    import numpy as np

    fs = extract_frames(video, n=4, side=448, sharp=0, cache_dir=tmp_path / "cache")
    xs = []
    for p in fs.paths:
        a = np.asarray(Image.open(p).convert("L"))
        xs.append(np.argwhere(a > 128)[:, 1].mean())
    assert xs == sorted(xs)


def test_sharp_frames_native_resolution(video, tmp_path):
    fs = extract_frames(video, n=8, side=448, sharp=2, cache_dir=tmp_path / "cache")
    assert len(fs.sharp_paths) == 2
    for p in fs.sharp_paths:
        with Image.open(p) as im:
            assert im.size == (640, 360)


def test_second_call_is_cached_and_fast(video, tmp_path):
    cache = tmp_path / "cache"
    first = extract_frames(video, n=8, side=448, sharp=2, cache_dir=cache)
    t0 = time.perf_counter()
    again = extract_frames(video, n=8, side=448, sharp=2, cache_dir=cache)
    assert time.perf_counter() - t0 < 0.2
    assert again.cached is True
    assert again.paths == first.paths and again.timestamps == first.timestamps
    assert again.sharp_paths == first.sharp_paths and all(p.exists() for p in again.paths)
    meta = json.loads((cache / "frames" / file_hash(video) / "meta.json").read_text())
    assert (meta["n"], meta["side"], meta["sharp"]) == (8, 448, 2)


def test_same_name_new_content_is_not_cached(tmp_path):
    """Stale state: re-encoding the same file name must not reuse the old frames."""
    cache = tmp_path / "cache"
    v = mf.make_video(tmp_path / "clip.mp4", seconds=2.0, color=(255, 255, 255))
    extract_frames(v, n=4, side=448, sharp=0, cache_dir=cache)
    v = mf.make_video(tmp_path / "clip.mp4", seconds=2.0, color=(255, 0, 0))
    again = extract_frames(v, n=4, side=448, sharp=0, cache_dir=cache)
    assert again.cached is False
    assert square_colour(again.paths[0]) == "red"


def square_colour(path) -> str:
    import numpy as np

    a = np.asarray(Image.open(path).convert("RGB")).reshape(-1, 3).astype(int)
    lit = a[a.max(axis=1) > 100]  # the square; the background is black
    r, g, b = lit.mean(axis=0)
    return "red" if r > 150 and g < 100 and b < 100 else "white" if min(r, g, b) > 150 else "other"


@pytest.mark.parametrize("change", [{"n": 16}, {"side": 224}, {"sharp": 2}])
def test_different_settings_not_cached(video, tmp_path, change):
    cache = tmp_path / "cache"
    base = {"n": 8, "side": 448, "sharp": 0}
    extract_frames(video, cache_dir=cache, **base)
    again = extract_frames(video, cache_dir=cache, **{**base, **change})
    assert again.cached is False and len(again.paths) == again_n(change, base)


def again_n(change, base):
    return change.get("n", base["n"])


def test_cache_with_missing_frame_files_rebuilds(video, tmp_path):
    cache = tmp_path / "cache"
    fs = extract_frames(video, n=4, side=448, sharp=0, cache_dir=cache)
    fs.paths[1].unlink()
    again = extract_frames(video, n=4, side=448, sharp=0, cache_dir=cache)
    assert again.cached is False and all(p.exists() for p in again.paths)


def test_unreadable_file(tmp_path):
    bad = tmp_path / "clip.mp4"
    bad.write_bytes(b"\x00not a video" * 100)
    with pytest.raises(UnsupportedFile, match=r"\.mp4"):
        extract_frames(bad, n=8, side=448, sharp=0, cache_dir=tmp_path / "cache")


def test_more_frames_than_the_clip_has(tmp_path):
    v = mf.make_video(tmp_path / "short.mp4", seconds=0.5, fps=10)  # 5 frames
    fs = extract_frames(v, n=16, side=448, sharp=0, cache_dir=tmp_path / "cache")
    assert 1 <= len(fs.paths) <= 5 and len(fs.timestamps) == len(fs.paths)
    assert fs.timestamps == sorted(set(fs.timestamps))


def test_file_hash_changes_with_content(tmp_path):
    a = tmp_path / "a.bin"
    a.write_bytes(b"x" * (3 * 1024 * 1024))
    h1 = file_hash(a)
    a.write_bytes(b"x" * (3 * 1024 * 1024 - 1) + b"y")
    assert file_hash(a) != h1 and len(h1) == 64
