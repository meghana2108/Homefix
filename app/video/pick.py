"""Pick the frame to count in, with plain code (no model).

Why: counts look at one whole frame (in 2x2 grids the 2B model counted the tiles). The middle frame
misses things that appear one at a time: on the practice pack it saw about half of them (3 of 4,
6 of 8) on the M2 (2026-11-19). The frame with the most edges is the one where the most things are
on screen: the last frame when things appear one by one, the busiest moment when they pass through.

Method: edge pixels = pixels whose horizontal + vertical grey-level change is above EDGE. The middle
frame is kept unless another frame has clearly more edges (MARGIN), so a still or noisy clip doesn't
jump around.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

EDGE = 40        # grey levels
MARGIN = 1.10    # another frame needs 10% more edge pixels than the middle one


def edge_pixels(path: Path) -> int:
    g = np.asarray(Image.open(path).convert("L"), dtype=np.int16)
    dx = np.abs(np.diff(g, axis=1))[:-1, :]
    dy = np.abs(np.diff(g, axis=0))[:, :-1]
    return int(((dx + dy) > EDGE).sum())


def busiest_frame(paths: list[Path]) -> int:
    """Index of the frame to count in: the middle one unless another has clearly more edges."""
    if not paths:
        raise ValueError("no frames")
    mid = len(paths) // 2
    counts = [edge_pixels(p) for p in paths]
    best = max(range(len(paths)), key=lambda i: (counts[i], -abs(i - mid)))
    return best if counts[best] > counts[mid] * MARGIN else mid
