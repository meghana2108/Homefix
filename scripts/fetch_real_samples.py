"""Fetch the real (not drawn) example files for the UI gallery, once per Mac. Setup only, never at runtime.

    uv run python scripts/fetch_real_samples.py            # download what's missing (slow: Wikimedia rate-limits)
    uv run python scripts/fetch_real_samples.py --from DIR # copy from another Mac's frontend/public/samples instead

Real photos, sounds and clips from Wikimedia Commons (CC0, public domain, CC BY, CC BY-SA), two US government
guides (public domain: EPA mold guide, CPSC carbon monoxide sheet) and a week of one real household's power use
(UCI "Individual household electric power consumption", CC BY 4.0). Every file's author, license and source page
is listed below and in frontend/src/examples.ts (shown under each example) and docs/ASSETS.md.

Writes frontend/public/samples/ (gitignored, like the drawn samples) and copies the two guides to data/manuals/
with short titles. Re-running skips files that are already there.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "frontend" / "public" / "samples"
MANUALS = ROOT / "data" / "manuals"
UA = {"User-Agent": "HomeFix-setup/1.0 (offline home-repair assistant; one-time sample download)"}
API = "https://commons.wikimedia.org/w/api.php"
GAP_S = 20          # between Commons downloads: Wikimedia answers 429 to bursts
BACKOFF_S = (60, 180, 300)


@dataclass(frozen=True)
class Commons:
    out: str            # file name in frontend/public/samples/
    title: str          # Commons file title, without "File:"
    kind: str           # photo | sound | video
    author: str
    license: str
    start: float = 0.0  # sound/video: where the clip starts (s)
    seconds: float = 10.0
    gain_db: float = 0.0  # sound only: raise a very quiet recording (0 = leave as is)


COMMONS = [
    Commons("real_thermostat_80_cool.jpg", "Hunter Non-Programmable Digital Thermostat.jpg", "photo", "Ente75", "CC0"),
    Commons("real_thermostat_66.jpg", "Robertshaw Non-Programmable Digital Thermostat.JPG", "photo", "Ente75", "CC0"),
    Commons("real_burner_glowing.jpg", "Electric stove coil with glass ceramic cooktop.jpg", "photo", "A.Savin",
            "CC BY-SA 3.0"),
    Commons("real_breaker_panel.jpg", "Eaton circuit breaker panel open.JPG", "photo", "BrokenSphere", "CC BY-SA 3.0"),
    Commons("real_microwave.jpg", "SilverCrest SMW 800 D4-2370.jpg", "photo", "Raimond Spekking", "CC BY-SA 4.0"),
    Commons("real_water_heater_label.jpg", "Water heater dial - Easy Set Thermostat, gas powered.jpg", "photo",
            "Jason Woodhead", "CC BY 2.0"),
    # Added for the #/demo walk-through (see DEMO_MEDIA).
    Commons("real_leaking_pipe.jpg", "Leaking pipe by Saltash Field - geograph.org.uk - 7324720.jpg", "photo",
            "Mr Ignavy", "CC BY-SA 2.0"),
    Commons("real_smoke_detector.jpg", "Smoke detector (1).JPG", "photo", "Georg Pik", "Public domain"),
    # Source is very quiet; the chirps in this window are at about 3 s and 8.6 s.
    Commons("real_smoke_alarm_chirp.wav", "Smoke detector alarm battery beep.webm", "sound", "JoBrodie",
            "CC BY-SA 4.0", start=38.0, seconds=9.0, gain_db=20.0),
]

ALLOWED_LICENSES = ("CC0", "Public domain", "CC BY ", "CC BY-SA ")
_NAME = re.compile(r"^[a-z0-9_]+\.(jpg|png|wav|mp4)$")
_KIND_EXT = {"photo": ("jpg", "png"), "sound": ("wav",), "video": ("mp4",)}

# The five files the #/demo scenes show and play; served at /samples/<name>.
DEMO_MEDIA = ("real_breaker_panel.jpg", "real_leaking_pipe.jpg", "real_thermostat_66.jpg",
              "real_smoke_detector.jpg", "real_smoke_alarm_chirp.wav")


def check_list(items: list[Commons]) -> list[str]:
    """Problems with the pinned Commons list: non-free license, duplicate or odd file name, kind vs extension."""
    problems: list[str] = []
    seen: set[str] = set()
    for c in items:
        if not (c.license.startswith(ALLOWED_LICENSES) or c.license in ("CC BY", "CC BY-SA")):
            problems.append(f"{c.out}: license {c.license!r} is not free (CC0, public domain, CC BY, CC BY-SA)")
        if c.out in seen:
            problems.append(f"{c.out}: listed twice")
        seen.add(c.out)
        if not _NAME.match(c.out):
            problems.append(f"{c.out}: name must match {_NAME.pattern}")
        elif c.out.rsplit(".", 1)[1] not in _KIND_EXT.get(c.kind, ()):
            problems.append(f"{c.out}: kind {c.kind!r} does not match the extension")
    return problems


@dataclass(frozen=True)
class Direct:
    out: str
    url: str
    author: str
    license: str
    manual_title: str | None = None  # also put on the manual shelf under this title


DIRECT = [
    Direct("epa_mold_guide.pdf", "https://www.epa.gov/sites/default/files/2016-10/documents/moldguide12.pdf",
           "US EPA (EPA 402-K-02-003)", "Public domain (US government work)",
           "EPA guide: mold, moisture and your home"),
    Direct("cpsc_carbon_monoxide.pdf", "https://www.cpsc.gov/s3fs-public/464.pdf",
           "US Consumer Product Safety Commission (CPSC 464)", "Public domain (US government work)",
           "CPSC: carbon monoxide, the invisible killer"),
]
MANUAL_STEMS = {"epa_mold_guide.pdf": "epa_mold_moisture_guide", "cpsc_carbon_monoxide.pdf": "cpsc_carbon_monoxide"}

POWER_ZIP = "https://archive.ics.uci.edu/static/public/235/individual+household+electric+power+consumption.zip"
POWER_CSV = "real_home_power_week.csv"
POWER_WEEK = ("2007-01-08", "2007-01-14")


def _get(url: str, timeout: int = 120) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def _patient(url: str) -> bytes:
    for wait in (0, *BACKOFF_S):
        time.sleep(wait)
        try:
            return _get(url)
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            print(f"    rate-limited, waiting {BACKOFF_S[0] if wait == 0 else wait} s", flush=True)
    raise SystemExit(f"Still rate-limited for {url}. Run again later, or use --from DIR.")


def _commons_url(a: Commons) -> str:
    q = {"action": "query", "format": "json", "titles": f"File:{a.title}", "prop": "imageinfo|videoinfo",
         "iiprop": "url", "viprop": "derivatives"}
    if a.kind == "photo":
        q["iiurlwidth"] = 1280
    page = next(iter(json.loads(_patient(f"{API}?{urllib.parse.urlencode(q)}"))["query"]["pages"].values()))
    info = page["imageinfo"][0]
    if a.kind == "photo":
        return info.get("thumburl", info["url"])
    if a.kind == "video":
        ders = [d for d in page.get("videoinfo", [{}])[0].get("derivatives", [])
                if d.get("height", 0) >= 360 and "webm" in d.get("type", "")]
        if ders:
            return min(ders, key=lambda d: d["height"])["src"]
    return info["url"]


def _ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


def fetch_commons(a: Commons, dest: Path) -> None:
    raw = _patient(_commons_url(a))
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "src"
        src.write_bytes(raw)
        if a.kind == "photo":
            from PIL import Image

            im = Image.open(src).convert("RGB")
            im.thumbnail((1280, 1280))
            im.save(dest, quality=88)
        elif a.kind == "sound":
            gain = ["-af", f"volume={a.gain_db}dB,alimiter=limit=0.95"] if a.gain_db else []
            _ffmpeg("-ss", str(a.start), "-t", str(a.seconds), "-i", str(src), *gain, "-ac", "1", "-ar", "16000",
                    str(dest))
        else:
            _ffmpeg("-ss", str(a.start), "-t", str(a.seconds), "-i", str(src), "-an", "-vf", "scale=640:-2",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(dest))


def power_week(dest: Path) -> None:
    """Hourly mean watts for one week of the UCI household (minute readings in kW)."""
    zf = zipfile.ZipFile(io.BytesIO(_get(POWER_ZIP, timeout=600)))
    acc: dict[str, list[float]] = defaultdict(list)
    with zf.open("household_power_consumption.txt") as f:
        for line in io.TextIOWrapper(f):
            d, t, p = line.split(";")[:3]
            if not d[:1].isdigit() or p == "?":
                continue
            dd, mm, yy = d.split("/")
            day = f"{yy}-{int(mm):02d}-{int(dd):02d}"
            if POWER_WEEK[0] <= day <= POWER_WEEK[1]:
                acc[f"{day}T{t[:2]}:00"].append(float(p))
    with dest.open("w", newline="") as o:
        w = csv.writer(o)
        w.writerow(["timestamp", "watts"])
        for k in sorted(acc):
            w.writerow([k, round(sum(acc[k]) / len(acc[k]) * 1000, 1)])


def shelve(pdf: Path, stem: str, title: str) -> None:
    """Copy a guide to data/manuals/ with a short title (the PDF's own titles are long catalog strings)."""
    import pymupdf

    MANUALS.mkdir(parents=True, exist_ok=True)
    with pymupdf.open(pdf) as d:
        meta = dict(d.metadata or {})
        meta["title"] = title
        d.set_metadata(meta)
        d.save(MANUALS / f"{stem}.pdf")


def names() -> list[str]:
    return [a.out for a in COMMONS] + [d.out for d in DIRECT] + [POWER_CSV]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--from", dest="src", type=Path, help="copy from another Mac's samples folder instead")
    a = ap.parse_args()
    problems = check_list(COMMONS)
    if problems:
        raise SystemExit("Pinned list problems:\n  " + "\n  ".join(problems))
    if shutil.which("ffmpeg") is None:
        raise SystemExit("Needs ffmpeg (brew install ffmpeg).")
    SAMPLES.mkdir(parents=True, exist_ok=True)
    for name in names():
        dest = SAMPLES / name
        if dest.exists() and dest.stat().st_size > 0:
            print(f"  have  {name}")
            continue
        if a.src:
            shutil.copyfile(a.src / name, dest)
            print(f"  copy  {name}")
            continue
        print(f"  fetch {name}", flush=True)
        c = next((x for x in COMMONS if x.out == name), None)
        d = next((x for x in DIRECT if x.out == name), None)
        if c:
            fetch_commons(c, dest)
            time.sleep(GAP_S)
        elif d:
            dest.write_bytes(_get(d.url))
        else:
            power_week(dest)
    for d in DIRECT:
        if d.manual_title:
            shelve(SAMPLES / d.out, MANUAL_STEMS[d.out], d.manual_title)
    print(f"Done: {len(names())} real samples in {SAMPLES.relative_to(ROOT)}, 2 guides in data/manuals/.")


if __name__ == "__main__":
    sys.exit(main())
