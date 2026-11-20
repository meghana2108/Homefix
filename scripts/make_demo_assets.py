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


WASHER_BUTTONS = ("Temp", "Spin", "Delay", "Start/Pause")
WASHER_KNOB = ("Cottons", "Synthetics", "Wool", "Quick 20'", "Spin")


def display_photo(code: str, seed: int = 3, buttons=WASHER_BUTTONS, knob=WASHER_KNOB,
                  units=("°C", "rpm"), body=(205, 207, 210), status: str | None = None) -> Image.Image:
    rng = np.random.default_rng(seed)
    W, H = 1600, 1000
    img = Image.new("RGB", (W, H), body)  # white-grey appliance front
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
    for i, label in enumerate(knob):
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
    if status:  # a lit status word under the digits, e.g. "COOKTOP ON"
        tw = d.textlength(status, font=font)
        d.text(((dx0 + dx1 - tw) / 2, dy1 + 8), status, fill=(240, 40, 40), font=font)
    # buttons and labels
    for i, name in enumerate(buttons):
        bx = 780 + i * 160
        d.rounded_rectangle((bx, 610, bx + 130, 680), radius=12, fill=(80, 84, 90))
        d.text((bx + 12, 625), name, fill=(230, 230, 230), font=small)
    d.text((1300, 360), units[0], fill=(200, 200, 200), font=font)
    d.text((1300, 470), units[1], fill=(200, 200, 200), font=font)
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


GUIDE_TITLE = "Unit 4B apartment guide: washer, heat and who to call"
# A sample landlord's guide, written by the HomeFix team (no real brand or building). Real manuals draw
# their error codes as display graphics (AEG, Electrolux and LG checked, 2026-11-19), so a text search
# can't find "E21" in them; a landlord's guide types them out. Everything here is our own text.
GUIDE_PAGES = [
    """Welcome to Unit 4B

Who to call
- Fire, smoke, or someone is hurt: leave the apartment and call 911.
- You smell gas: do not use switches or flames. Leave the building, then call the gas company
  emergency line at 1-800-555-0142 from outside.
- Water leak or no heat: call the maintenance line at (207) 555-0199, any time, day or night.
- Anything else (a broken blind, a slow drain, a noisy fan): email maintenance@unit4b.example.
  Repairs that are not urgent are booked within 3 working days.

Your appliances
- Washer: model BW-200, in the hall closet. Error codes and beeps are on page 2.
- Electric panel (breakers): in the kitchen, behind the door. See page 4.
- Smoke alarm: hallway ceiling. See page 4.

Rent is due on the 1st of each month. The lease, not this guide, decides who pays for a repair.""",
    """Washer BW-200: beeps and error codes

Five short beeps at the end of a cycle mean the cycle has finished. This is normal.
A long beep with a code on the display means the washer has stopped. Find the code below.

Error codes on the display
E10 - The washer is not filling with water. Make sure both faucets behind the washer are fully open,
      then press Start/Pause.
E21 - The washer cannot drain the water. Turn the washer off and unplug it. Clean the drain pump
      filter behind the small door at the bottom right (see page 3). Then check that the drain hose
      is not kinked. If E21 comes back after cleaning the filter, call the maintenance line.
E40 - The door is not closed. Close the door firmly until it clicks, then press Start/Pause.
E52 - Too much detergent: too many suds. Run a Rinse cycle with no detergent, and use less next time.
E90 - Electronic fault. Unplug the washer for 1 minute, then plug it back in. If E90 stays,
      call the maintenance line.

Do not open the washer's back panel. Only maintenance staff may repair the washer.""",
    """Washer BW-200: cleaning the drain pump filter

Do this when the display shows E21, or once a month.
1. Turn the washer off and unplug it. Let the water cool down if you used a hot cycle.
2. Put a towel and a shallow tray under the small door at the bottom right of the washer.
3. Open the small door. Pull out the short black hose and remove its cap. Let the water run into the tray.
4. Turn the filter counterclockwise and pull it out. Expect more water.
5. Rinse the filter under the tap and remove lint, coins and hair.
6. Put the filter back, turn it clockwise until it is tight, cap the hose and close the door.
7. Plug the washer in and run a Rinse and Spin cycle to check that it drains.""",
    """Heat, breakers and the smoke alarm

No heat: check that the thermostat is set to Heat and above room temperature. If the radiators stay
cold for more than one hour, call the maintenance line.

A breaker trips (part of the apartment loses power): unplug what you were using. In the electric
panel, push the switch that is in the middle position fully to OFF, then back to ON. If it trips again,
leave it off and call the maintenance line. Never tape a breaker on.

The smoke alarm chirps once every 30 to 60 seconds: its battery is low. Tell maintenance; do not
remove the alarm. A loud, continuous alarm means smoke: leave and call 911.""",
]


def apartment_guide(path: Path) -> Path:
    import pymupdf

    doc = pymupdf.open()
    for n, text in enumerate(GUIDE_PAGES, start=1):
        page = doc.new_page(width=612, height=792)
        title, _, body = text.partition("\n\n")
        page.insert_text((54, 72), title, fontsize=17, fontname="helv")
        page.insert_textbox(pymupdf.Rect(54, 92, 558, 740), body, fontsize=10.5, fontname="helv", lineheight=1.35)
        page.insert_text((54, 760), f"Unit 4B apartment guide - sample written by the HomeFix team - page {n}",
                          fontsize=8, fontname="helv")
    doc.set_metadata({"title": GUIDE_TITLE, "author": "HomeFix team (sample)"})
    doc.save(path)
    return path


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
    manuals = OUT.parent.parent / "manuals"
    manuals.mkdir(parents=True, exist_ok=True)
    guide = apartment_guide(manuals / "apartment_guide_unit_4b.pdf")
    print(f"wrote {beep}\nwrote {photo}\nwrote {close}\nwrote {guide}")


if __name__ == "__main__":
    main()
