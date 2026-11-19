"""Measure which way the main moving thing goes, with plain code (no model).

Why: on qwen3-vl:2b, frames tiled into grids were read as motion between tiles ("down",
"clockwise" for a square moving right). With this measurement in the prompt it answered all
four directions right on the M2 (2026-11-19).

Method: background = per-pixel median over the frames; the moving region in each frame = pixels
that differ from it by more than DIFF. Its centre from first to last frame gives
left/right/up/down; if the centre barely moves, a growing / shrinking region gives toward / away.
Rotation (clockwise) is not measured.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

DIFF = 30            # grey levels
MIN_PIXELS = 20      # smaller changes are noise
MIN_SHIFT = 0.05     # of the frame width: less than this is "not moving sideways"
GROWTH = 1.3         # area ratio for toward / away


def measure_motion(paths: list[Path]) -> str | None:
    """'left' | 'right' | 'up' | 'down' | 'toward' | 'away', or None when nothing clearly moves."""
    if len(paths) < 2:
        return None
    frames = [np.asarray(Image.open(p).convert("L"), dtype=np.float32) for p in paths]
    if len({f.shape for f in frames}) != 1:
        return None
    background = np.median(np.stack(frames), axis=0)
    track = []
    for f in frames:
        moving = np.abs(f - background) > DIFF
        n = int(moving.sum())
        if n > MIN_PIXELS:
            ys, xs = np.nonzero(moving)
            track.append((float(xs.mean()), float(ys.mean()), n))
    if len(track) < 2:
        return None
    (x0, y0, a0), (x1, y1, a1) = track[0], track[-1]
    dx, dy = x1 - x0, y1 - y0
    if max(abs(dx), abs(dy)) < MIN_SHIFT * frames[0].shape[1]:
        if a1 > GROWTH * a0:
            return "toward"
        if a1 < a0 / GROWTH:
            return "away"
        return None
    if abs(dx) >= abs(dy):
        return "right" if dx > 0 else "left"
    return "down" if dy > 0 else "up"
