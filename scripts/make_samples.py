"""Make the example files for the UI's example gallery and the sample manuals. Everything here is made by us
(MIT): synthetic photos, sounds, voice notes (macOS `say`, offline), clips, a lease, a CSV, and four short
appliance guides with their codes typed out. No real brand, building or person.

    uv run python scripts/make_samples.py

Writes frontend/public/samples/ and data/manuals/*.pdf. Both are gitignored (the hard-rule test bans tracked
.wav/.mp4/.pdf), so this script is how either Mac gets them. frontend/src/examples.ts lists what the gallery shows.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_demo_assets as demo

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "frontend" / "public" / "samples"
MANUALS = ROOT / "data" / "manuals"
SR = 16000


# ---------------------------------------------------------------- PDFs
def guide_pdf(path: Path, title: str, pages: list[str], footer: str) -> Path:
    """A plain text PDF: each page is "<heading>\\n\\n<body>". The title goes in the PDF metadata."""
    import pymupdf

    doc = pymupdf.open()
    for n, text in enumerate(pages, start=1):
        page = doc.new_page(width=612, height=792)
        head, _, body = text.partition("\n\n")
        page.insert_text((54, 72), head, fontsize=17, fontname="helv")
        page.insert_textbox(pymupdf.Rect(54, 92, 558, 740), body, fontsize=10.5, fontname="helv", lineheight=1.35)
        page.insert_text((54, 760), f"{footer} - page {n}", fontsize=8, fontname="helv")
    doc.set_metadata({"title": title, "author": "HomeFix team (sample)"})
    doc.save(path)
    return path


DISHWASHER = ("Dishwasher DW-50 quick guide", [
    """Dishwasher DW-50: lights and codes

The display shows a code when the dishwasher stops by itself. Find it below.
E1 - Water is not coming in. Check that the water valve under the sink is open, then press Start.
E4 - The spray arm is blocked. Open the door and turn the spray arms by hand. Remove anything that stops them.
E9 - The door was opened during the cycle. Close the door firmly and press Start to continue.
E15 - Water is in the base of the dishwasher (a leak). Turn the dishwasher off at the switch and close the
      water valve under the sink. Do not run it again. Call the maintenance line.
E24 - The dishwasher cannot drain. Clean the filter in the bottom of the tub (page 2), then run Rinse.

Three short beeps at the end of a program mean the dishes are done. This is normal.""",
    """Dishwasher DW-50: cleaning the filter

Clean the filter once a month, or when the display shows E24.
1. Turn the dishwasher off and let it cool.
2. Take out the lower basket.
3. Turn the round filter in the bottom of the tub counterclockwise and lift it out.
4. Rinse it under the tap. Use a soft brush for grease. Do not use a wire brush.
5. Put the filter back and turn it clockwise until it locks.

Use dishwasher detergent only. Dish soap makes too much foam and can make the dishwasher leak.""",
], "Dishwasher DW-50 quick guide - sample written by the HomeFix team")

THERMOSTAT = ("Thermostat T-100 guide", [
    """Thermostat T-100: the display

The large number is the room temperature. SET shows the temperature you asked for.
LO flashing - the batteries are low. Replace both AA batteries within two weeks. The heating still works.
HI - the room is above 90°F. Check that no heater is placed under the thermostat.
E2 - the thermostat cannot reach the boiler. Call the maintenance line.
Snowflake - cooling mode. Flame - heating mode. Press MODE to switch.""",
    """Thermostat T-100: setting the temperature

Press the up or down arrow to change the set temperature by one degree.
To save energy, set 68°F when you are home and 62°F at night or when you are away.
Each degree lower saves about 3% on heating.
Hold MODE for 3 seconds to turn the heating off. The display then shows OFF.
To change the batteries, pull the thermostat straight off the wall plate. Use two AA batteries.""",
], "Thermostat T-100 guide - sample written by the HomeFix team")

ALARM = ("Smoke and CO alarm guide", [
    """Smoke and carbon monoxide alarm: what the sounds mean

Three long beeps, repeating: SMOKE or FIRE. Leave the apartment now and call 911 from outside.
Four short beeps, repeating: CARBON MONOXIDE. Go outside into fresh air now and call 911.
One short chirp every 30 to 60 seconds: the battery is low. Tell maintenance. The alarm still works.
Five chirps every minute: the alarm is at the end of its life (10 years). Tell maintenance to replace it.

Never take the alarm down or remove its battery to stop a chirp.""",
    """Smoke and carbon monoxide alarm: testing it

Press and hold the TEST button for 5 seconds once a month. The alarm sounds loudly, then stops.
If it stays silent, tell maintenance the same day.
Cooking smoke can set off the alarm. Open a window and fan the air. Press HUSH to silence it for 8 minutes.
Never press HUSH if you do not know where the smoke is coming from.""",
], "Smoke and CO alarm guide - sample written by the HomeFix team")

LEASE_PAGES = [
    """Sample lease summary: Unit 4B, 12 Harbor Street

Tenant: the student renting Unit 4B. Landlord: Harbor Street Rentals.
Term: 12 months, from September 1 to August 31.
Rent: $1,450 per month, due on the 1st. A late fee of $50 applies after the 5th.
Security deposit: $1,450, returned within 30 days after you move out, minus the cost of any damage.

Moving out
You must give written notice at least 60 days before you move out. Email is accepted.
Leave the apartment clean and return both keys and the mailbox key.""",
    """Repairs, pets and guests

Repairs: report problems to maintenance within 48 hours. The landlord pays for repairs to appliances and
plumbing unless the tenant caused the damage. Emergencies (no heat, a leak, no power): call any time.
Pets: one cat is allowed with a $300 pet deposit. Dogs are not allowed.
Guests: guests may stay up to 14 nights in a row. Longer stays need the landlord's written consent.
Smoking is not allowed anywhere in the building.
Quiet hours are from 10 pm to 7 am.""",
]


# ---------------------------------------------------------------- photos
def small_jpg(img: Image.Image, path: Path, width: int = 900) -> Path:
    img = img.convert("RGB")
    img.thumbnail((width, width))
    img.save(path, quality=82, optimize=True)
    return path


def one_pixel_edit(src: Path, dst: Path) -> Path:
    """For the repair-request demo: the same photo with one pixel changed. It looks identical; its SHA-256
    fingerprint doesn't match, so "Check a file against this request" says it was changed."""
    im = Image.open(src).convert("RGB")
    r, g, b = im.getpixel((10, 10))
    im.putpixel((10, 10), ((r + 40) % 256, g, b))
    im.save(dst, quality=95)
    return dst


def closeup(img: Image.Image) -> Image.Image:
    return img.crop((640, 230, 1420, 700)).resize((1170, 705), Image.Resampling.LANCZOS)


def stove_photo(on: tuple[bool, ...] = (True, False, True, False), seed: int = 5) -> Image.Image:
    """A glass cooktop from above with four burners; the ones that are on glow red-orange."""
    rng = np.random.default_rng(seed)
    W, H = 1200, 900
    img = Image.new("RGB", (W, H), (24, 24, 26))
    d = ImageDraw.Draw(img)
    centres = [(330, 280), (870, 280), (330, 640), (870, 640)]
    for (cx, cy), lit in zip(centres, on):
        r = 170 if cx < 600 else 140
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(90, 90, 95), width=6)
        if lit:
            for k in range(6, 0, -1):
                rr = r - 20 - k * 12
                c = (min(255, 180 + k * 12), 60 + k * 8, 20)
                d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=c, width=10)
    img = img.filter(ImageFilter.GaussianBlur(2.2))
    a = np.asarray(img).astype(np.float32) + rng.normal(0, 4, (H, W, 3))
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


# ---------------------------------------------------------------- sounds
def smoke_chirp(seconds: float = 12.0) -> np.ndarray:
    """One short 3.2 kHz chirp every 4 s, the low-battery chirp, over a quiet room."""
    t = np.arange(int(seconds * SR)) / SR
    y = np.random.default_rng(1).normal(0, 0.003, t.size)
    for start in np.arange(0.5, seconds, 4.0):
        i0, n = int(start * SR), int(0.09 * SR)
        tt = np.arange(n) / SR
        y[i0:i0 + n] += 0.5 * np.sin(2 * np.pi * 3200 * tt) * np.hanning(n)
    return y.astype(np.float32)


def dripping(seconds: float = 10.0, seed: int = 2) -> np.ndarray:
    """Water drops into a sink: short plops with a falling pitch, at uneven gaps."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(seconds * SR)) / SR
    y = rng.normal(0, 0.004, t.size)
    pos = 0.3
    while pos < seconds - 0.3:
        n = int(0.12 * SR)
        tt = np.arange(n) / SR
        f = 1400 * np.exp(-tt * 9) + 500
        y[int(pos * SR):int(pos * SR) + n] += 0.45 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 35)
        pos += rng.uniform(0.45, 0.9)
    return y.astype(np.float32)


def say_wav(path: Path, text: str, voice: str | None = None) -> Path:
    with tempfile.TemporaryDirectory() as tmp:
        aiff = Path(tmp) / "v.aiff"
        cmd = ["say", "-o", str(aiff)] + (["-v", voice] if voice else []) + [text]
        subprocess.run(cmd, check=True, timeout=60)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(aiff), "-ac", "1", "-ar", "16000", str(path)],
                       check=True)
    return path


# ---------------------------------------------------------------- clips
def write_clip(path: Path, frames: list[np.ndarray], fps: int = 10) -> Path:
    import cv2

    h, w = frames[0].shape[:2]
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "raw.mp4"
        out = cv2.VideoWriter(str(raw), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
        for f in frames:
            out.write(f[..., ::-1])
        out.release()
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-an", "-crf", "30", str(path)], check=True)
    return path


def drip_clip(seconds: float = 5.0, fps: int = 10) -> list[np.ndarray]:
    """A pipe at the top; one blue drop falls from it to a puddle, again and again."""
    w, h = 480, 360
    frames = []
    for i in range(int(seconds * fps)):
        img = Image.new("RGB", (w, h), (236, 232, 224))
        d = ImageDraw.Draw(img)
        d.rectangle((0, 30, w, 60), fill=(120, 124, 130))       # the pipe
        d.ellipse((150, 320, 330, 350), fill=(110, 160, 220))   # the puddle
        y = 70 + ((i * 18) % 240)
        d.ellipse((228, y, 252, y + 34), fill=(40, 110, 210))   # the drop
        frames.append(np.asarray(img))
    return frames


def lights_clip(n_lights: int = 4, seconds: float = 6.0, fps: int = 10) -> list[np.ndarray]:
    """A dark panel; warning lights come on one at a time and stay on."""
    w, h = 480, 270
    frames = []
    total = int(seconds * fps)
    for i in range(total):
        img = Image.new("RGB", (w, h), (30, 32, 36))
        d = ImageDraw.Draw(img)
        on = min(n_lights, 1 + i * n_lights // int(total * 0.8))
        for k in range(n_lights):
            x = 70 + k * 100
            d.ellipse((x, 100, x + 60, 160), fill=(255, 170, 30) if k < on else (55, 57, 60))
        frames.append(np.asarray(img))
    return frames


def smartplug_week() -> str:
    """Hourly watts for one week from a fridge on a smart plug: a daily cycle, plus one bad night."""
    rng = np.random.default_rng(4)
    rows = ["timestamp,watts"]
    for day in range(7):
        for hour in range(24):
            base = 95 + 25 * np.sin((hour - 15) / 24 * 2 * np.pi) + rng.normal(0, 6)
            if day == 3 and hour in (2, 3):  # the door was left open
                base += 260
            rows.append(f"2026-11-{9 + day:02d}T{hour:02d}:00,{base:.1f}")
    return "\n".join(rows) + "\n"


def main() -> None:
    if shutil.which("say") is None or shutil.which("ffmpeg") is None:
        raise SystemExit("Needs macOS `say` and ffmpeg.")
    SAMPLES.mkdir(parents=True, exist_ok=True)
    MANUALS.mkdir(parents=True, exist_ok=True)
    out: list[Path] = []

    # manuals (gitignored folder) and the lease (a file to attach)
    out.append(demo.apartment_guide(MANUALS / "apartment_guide_unit_4b.pdf"))
    for stem, (title, pages) in {"dishwasher_dw50": DISHWASHER[:2], "thermostat_t100": THERMOSTAT[:2],
                                 "smoke_co_alarm": ALARM[:2]}.items():
        footer = {"dishwasher_dw50": DISHWASHER, "thermostat_t100": THERMOSTAT, "smoke_co_alarm": ALARM}[stem][2]
        out.append(guide_pdf(MANUALS / f"{stem}.pdf", title, pages, footer))
    out.append(guide_pdf(SAMPLES / "lease_unit_4b.pdf", "Sample lease summary, Unit 4B", LEASE_PAGES,
                         "Sample lease summary - written by the HomeFix team, not a real lease"))

    # photos
    out.append(small_jpg(closeup(demo.display_photo("E21")), SAMPLES / "washer_display_e21.jpg"))
    out.append(one_pixel_edit(SAMPLES / "washer_display_e21.jpg", SAMPLES / "washer_display_e21_edited.jpg"))
    out.append(small_jpg(closeup(demo.display_photo(
        "E24", seed=8, buttons=("Eco", "Auto", "Rinse", "Start"), knob=("Eco", "Auto", "Glass", "Quick", "Rinse"),
        units=("h", "min"), body=(225, 226, 228))), SAMPLES / "dishwasher_display_e24.jpg"))
    out.append(small_jpg(closeup(demo.display_photo(
        "68", seed=11, buttons=("Mode", "Fan", "Down", "Up"), knob=("Off", "Heat", "Cool", "Auto", "Fan"),
        units=("°F", "SET"), body=(238, 236, 230))), SAMPLES / "thermostat_68.jpg"))
    out.append(small_jpg(stove_photo(), SAMPLES / "stove_two_on.jpg"))
    out.append(small_jpg(closeup(demo.display_photo(
        "832", seed=5, buttons=("Light", "Start", "Cancel", "Lock"), knob=("Bake", "Broil", "Warm", "Clean", "Off"),
        units=("", ""), body=(196, 198, 200), status="COOKTOP ON")), SAMPLES / "cooktop_clock.jpg"))

    # sounds and voice notes
    sf.write(SAMPLES / "washer_done_beeps.wav", demo.washer_beep(), SR)
    sf.write(SAMPLES / "smoke_alarm_chirp.wav", smoke_chirp(), SR)
    sf.write(SAMPLES / "water_dripping.wav", dripping(), SR)
    out += [SAMPLES / "washer_done_beeps.wav", SAMPLES / "smoke_alarm_chirp.wav", SAMPLES / "water_dripping.wav"]
    out.append(say_wav(SAMPLES / "voicemail_neighbor.wav",
                       "Hi, this is Sam from apartment 3A, right below you. Water is dripping from my bathroom "
                       "ceiling. Could you check under your sink, and call me back? Thanks."))
    out.append(say_wav(SAMPLES / "voicemail_landlord.wav",
                       "Hi, it's Dana from Harbor Street Rentals. The plumber is coming on Thursday between nine and "
                       "eleven in the morning to fix the kitchen sink. Please make sure someone can let him in."))

    # clips
    out.append(write_clip(SAMPLES / "pipe_dripping.mp4", drip_clip()))
    out.append(write_clip(SAMPLES / "warning_lights.mp4", lights_clip()))

    # data
    (SAMPLES / "fridge_smartplug_week.csv").write_text(smartplug_week())
    out.append(SAMPLES / "fridge_smartplug_week.csv")

    for p in out:
        print(f"{p.stat().st_size / 1024:7.0f} KB  {p.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
