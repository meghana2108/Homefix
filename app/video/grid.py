"""Tile video frames 2x2 into one image, numbering each tile with its frame number.

Why: qwen3-vl in Ollama costs ~1,050 prompt tokens per image whatever its size, so 8 separate
frames (8,394 tokens, 94 s on the M2) overflow lite's num_ctx 8192 and the 90 s timeout. Two
2x2 grids of the same 8 frames cost ~2,200 tokens. Grey gutters keep the panels apart: without
them a dark clip's four panels read as one scene (four squares, moving "down").
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _font(size: int):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


GUTTER = 12
GUTTER_COLOUR = (128, 128, 128)


def make_grids(paths: list[Path], out_dir: Path, first_number: int = 1, per_side: int = 2) -> list[Path]:
    """Group frames in fours (time order: top-left, top-right, bottom-left, bottom-right) and write
    one JPEG per group to out_dir as grid_<first>-<last>.jpg. Unused tiles stay black."""
    if not paths:
        return []
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(paths[0]) as im:
        tw, th = im.size
    per = per_side * per_side
    font = _font(max(14, th // 9))
    grids: list[Path] = []
    for start in range(0, len(paths), per):
        group = paths[start:start + per]
        size = (tw * per_side + GUTTER * (per_side - 1), th * per_side + GUTTER * (per_side - 1))
        grid = Image.new("RGB", size, GUTTER_COLOUR)
        for k in range(per):  # unused tiles stay black
            x, y = (k % per_side) * (tw + GUTTER), (k // per_side) * (th + GUTTER)
            grid.paste((0, 0, 0), (x, y, x + tw, y + th))
        draw = ImageDraw.Draw(grid)
        for k, p in enumerate(group):
            x, y = (k % per_side) * (tw + GUTTER), (k // per_side) * (th + GUTTER)
            with Image.open(p) as im:
                grid.paste(im.convert("RGB").resize((tw, th)), (x, y))
            label = str(first_number + start + k)
            box = draw.textbbox((x + 6, y + 2), label, font=font)
            draw.rectangle((box[0] - 4, box[1] - 2, box[2] + 4, box[3] + 2), fill="black")
            draw.text((x + 6, y + 2), label, fill="white", font=font)
        a, b = first_number + start, first_number + start + len(group) - 1
        out = out_dir / f"grid_{a:02d}-{b:02d}.jpg"
        grid.save(out, quality=90)
        grids.append(out)
    return grids
