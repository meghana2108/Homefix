"""Make the synthetic demo assets: a washer end-of-cycle beep and a photo of a washer display
showing an error code. Made by us (MIT). The outputs are media, so they stay out of git
(data/assets/private/ is gitignored); this script is how either Mac rebuilds them.

    uv run python scripts/make_demo_assets.py            # code E21
    uv run python scripts/make_demo_assets.py --code E20

These are stand-ins. A real recording of a washer and a real phone photo of a display are
better demo material; drop them in data/assets/private/ and list them in docs/ASSETS.md.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "assets" / "private"
SR = 16000


# ---------------------------------------------------------------- beep
def washer_beep(seed: int = 7) -> np.ndarray:
    """Five 2.4 kHz beeps (0.35 s on, 0.35 s off) over a soft drum-motor hum and water noise.
    Checked with CLAP on 2026-11-19: 'washing machine beeping' is the top label (20%)."""
    rng = np.random.default_rng(seed)

    def tone(f: float, d: float) -> np.ndarray:
        t = np.arange(int(SR * d)) / SR
        env = np.minimum(1, np.minimum(t, d - t) / 0.01)  # 10 ms fades, no clicks
        return 0.5 * env * np.sin(2 * np.pi * f * t)

    def sil(d: float) -> np.ndarray:
        return np.zeros(int(SR * d))

    sig = np.concatenate([sil(0.5)] + [np.concatenate([tone(2400, 0.35), sil(0.35)])] * 5 + [sil(0.8)])
    t = np.arange(len(sig)) / SR
    hum = (0.06 * np.sin(2 * np.pi * 55 * t) + 0.04 * np.sin(2 * np.pi * 110 * t)
           + 0.03 * np.convolve(rng.standard_normal(len(sig)), np.ones(40) / 40, "same"))
    sig = sig + 0.6 * hum
    return (sig / np.abs(sig).max() * 0.8).astype(np.float32)


# ---------------------------------------------------------------- display photo
# Seven-segment layout: a top, b top-right, c bottom-right, d bottom, e bottom-left, f top-left, g middle
SEGMENTS = {
    "0": "abcdef", "1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc", "5": "afgcd", "6": "afgedc",
    "7": "abc", "8": "abcdefg", "9": "abcdfg", "E": "afged", "F": "afge", "C": "afed", "H": "fbgec",
    "U": "fedcb", "L": "fed", "P": "abfge", "-": "g",
}


def _segment_polys(x: float, y: float, w: float, h: float, t: float, g: float = 3.0
                   ) -> dict[str, list[tuple[float, float]]]:
    """Hexagonal segments of one digit cell (x, y top-left; w, h size; t thickness; g gap), drawn
    long and joined like a real 7-segment display (short blobs read as noise to the model)."""
    h2 = t / 2

    def horiz(cy):
        x0, x1 = x + h2 + g, x + w - h2 - g
        return [(x0, cy), (x0 + h2, cy - h2), (x1 - h2, cy - h2), (x1, cy), (x1 - h2, cy + h2), (x0 + h2, cy + h2)]

    def vert(cx, y0, y1):
        y0, y1 = y0 + g, y1 - g
        return [(cx, y0), (cx + h2, y0 + h2), (cx + h2, y1 - h2), (cx, y1), (cx - h2, y1 - h2), (cx - h2, y0 + h2)]

    top, mid, bot = y + h2, y + h / 2, y + h - h2
    left, right = x + h2, x + w - h2
    return {"a": horiz(top), "g": horiz(mid), "d": horiz(bot),
            "f": vert(left, top, mid), "b": vert(right, top, mid),
            "e": vert(left, mid, bot), "c": vert(right, mid, bot)}


def display_photo(code: str, seed: int = 3) -> Image.Image:
    rng = np.random.default_rng(seed)
    W, H = 1600, 1000
    img = Image.new("RGB", (W, H), (205, 207, 210))  # white-grey washer front
    d = ImageDraw.Draw(img)
    # control panel strip
    d.rounded_rectangle((90, 230, W - 90, 760), radius=36, fill=(52, 55, 60))
    try:
        font = ImageFont.load_default(size=34)
        small = ImageFont.load_default(size=26)
    except TypeError:
        font = small = ImageFont.load_default()
    # programme knob
    d.ellipse((180, 330, 500, 650), fill=(185, 188, 192), outline=(30, 30, 30), width=6)
    d.ellipse((230, 380, 450, 600), fill=(160, 163, 168))
    d.line((340, 395, 340, 470), fill=(40, 40, 40), width=10)
    for i, label in enumerate(["Cottons", "Synthetics", "Wool", "Quick 20'", "Spin"]):
        a = np.deg2rad(205 + i * 32)
        tw = d.textlength(label, font=small)
        d.text((340 + 225 * np.cos(a) - tw / 2, 490 + 215 * np.sin(a) - 14), label, fill=(225, 225, 225), font=small)
    # display window
    dx0, dy0, dx1, dy1 = 760, 330, 1260, 560
    d.rounded_rectangle((dx0, dy0, dx1, dy1), radius=14, fill=(18, 22, 20))
    # digits: dim "8"s behind, lit code in front (like a real LCD/LED panel)
    cells = max(3, len(code))
    cw, ch, gap, thick = 105, 180, 34, 24
    x = dx0 + (dx1 - dx0 - (cells * cw + (cells - 1) * gap)) / 2
    y = dy0 + (dy1 - dy0 - ch) / 2
    lit, dim = (255, 92, 36), (22, 24, 22)  # unlit segments barely show, like an LED panel
    for k in range(cells):
        ch_ = code[k] if k < len(code) else " "
        polys = _segment_polys(x + k * (cw + gap), y, cw, ch, thick)
        for name, poly in polys.items():
            d.polygon(poly, fill=lit if name in SEGMENTS.get(ch_.upper(), "") else dim)
    # buttons and labels
    for i, label in enumerate(["Temp", "Spin", "Delay", "Start/Pause"]):
        bx = 780 + i * 160
        d.rounded_rectangle((bx, 610, bx + 130, 680), radius=12, fill=(80, 84, 90))
        d.text((bx + 12, 625), label, fill=(230, 230, 230), font=small)
    d.text((1300, 360), "°C", fill=(200, 200, 200), font=font)
    d.text((1300, 470), "rpm", fill=(200, 200, 200), font=font)
    # look like a phone photo: glow, slight tilt, crop, uneven light, blur, sensor noise
    glow = img.filter(ImageFilter.GaussianBlur(6))
    img = Image.blend(img, glow, 0.25)
    img = img.rotate(-3.5, resample=Image.Resampling.BICUBIC, fillcolor=(190, 192, 195))
    img = img.crop((40, 40, W - 40, H - 40))
    a = np.asarray(img).astype(np.float32)
    yy, xx = np.mgrid[0:a.shape[0], 0:a.shape[1]]
    light = 0.82 + 0.25 * np.exp(-(((xx - a.shape[1] * 0.7) / 700) ** 2 + ((yy - a.shape[0] * 0.3) / 500) ** 2))
    a = a * light[..., None] + rng.normal(0, 5, a.shape)
    img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.1))
    return img


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", default="E21", help="error code on the display (digits, E F C H U L P -)")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    beep = OUT / "washer_end_of_cycle_beep_synthetic.wav"
    sf.write(beep, washer_beep(), SR)
    img = display_photo(a.code)
    photo = OUT / f"washer_display_{a.code.lower()}_synthetic.jpg"
    img.save(photo, quality=88)
    # close-up: what a renter actually photographs (display and the buttons under it)
    close = OUT / f"washer_display_{a.code.lower()}_closeup_synthetic.jpg"
    img.crop((640, 230, 1420, 700)).resize((1170, 705), Image.Resampling.LANCZOS).save(close, quality=88)
    print(f"wrote {beep}\nwrote {photo}\nwrote {close}")


if __name__ == "__main__":
    main()
