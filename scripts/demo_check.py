"""Before the judges arrive: wait for the warm-up, then ask one question of each kind through the running API,
the way the demo will, and print how long each took and what came back.

    uv run uvicorn app.api.main:app --port 8000        # in one terminal (on the M4: PROFILE=full)
    uv run python scripts/demo_check.py                # in another, 5 minutes before the demo

Every answer it gets is also the warm-up for that path. Exit code 1 if anything failed or was slow.
Needs the gallery samples (scripts/make_samples.py, scripts/fetch_real_samples.py).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "frontend" / "public" / "samples"

# (what, question, sample file or None, what a good answer looks like, slow after warm-up (s))
CHECKS = [
    ("Photo + manual", "My washer shows this code. What should I do?", "washer_display_e21.jpg", "citation", 20),
    ("Sound", "Something in my hallway keeps chirping every minute. What's wrong?", "smoke_alarm_chirp.wav",
     "sound_labels", 10),
    ("Voice note", "When is the plumber coming?", "voicemail_landlord.wav", "transcript", 20),
    ("Document", "Can I have a cat?", "lease_unit_4b.pdf", "citation", 15),
    ("Manual, no file", "What should I do if a breaker trips?", None, "citation", 15),
    ("Danger", "I smell gas in the kitchen", None, "refusal:safety", 3),
    ("Code", "Write a function that converts a temperature from Fahrenheit to Celsius.", None, "code_result", 45),
    ("Photo after code", "How many burners are on?", "stove_two_on.jpg", "final", 20),
    ("Video", "Which way is the water moving?", "pipe_dripping.mp4", "frames", 60),
]


def wait_ready(api: str, limit_s: int) -> bool:
    t0 = time.time()
    last = ""
    while time.time() - t0 < limit_s:
        try:
            w = httpx.get(f"{api}/api/health", timeout=5).json().get("warm") or {}
        except httpx.HTTPError:
            w = {}
        steps = w.get("steps") or []
        line = " | ".join(f"{s['label']}: {s['state']}" for s in steps) or "waiting for the API"
        if line != last:
            print(f"  [{time.time() - t0:5.1f} s] {line}", flush=True)
            last = line
        if w.get("done"):
            return all(s["state"] == "ready" for s in steps)
        time.sleep(1)
    return False


def ask(api: str, question: str, sample: str | None) -> tuple[float, dict[str, dict]]:
    files = [("files", (sample, (SAMPLES / sample).read_bytes()))] if sample else None
    data = {"message": question, "manual_id": "auto"}
    seen: dict[str, dict] = {}
    t0 = time.time()
    with httpx.stream("POST", f"{api}/api/chat", data=data, files=files, timeout=300) as r:
        for line in r.iter_lines():
            if line.startswith("data:"):
                ev = json.loads(line[5:])
                seen.setdefault(ev["type"], ev)
    return time.time() - t0, seen


def good(seen: dict[str, dict], want: str) -> bool:
    if want.startswith("refusal:"):
        return seen.get("refusal", {}).get("reason") == want.split(":", 1)[1]
    if want == "code_result":
        return bool(seen.get("code_result", {}).get("passed"))
    return want in seen and "error" not in seen


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    ap.add_argument("--wait", type=int, default=300, help="seconds to wait for the warm-up")
    a = ap.parse_args()
    missing = [s for _, _, s, _, _ in CHECKS if s and not (SAMPLES / s).exists()]
    if missing:
        print(f"Missing samples: {', '.join(missing)}. Run scripts/make_samples.py and scripts/fetch_real_samples.py.")
        return 1
    print("Warm-up:")
    ready = wait_ready(a.api, a.wait)
    print("  all models ready" if ready else "  NOT all models ready (see above)")
    print("\nOne question of each kind:")
    bad = 0
    for what, question, sample, want, slow in CHECKS:
        secs, seen = ask(a.api, question, sample)
        ok = good(seen, want)
        fast = secs <= slow
        bad += (not ok) + (not fast)
        clarify = " (asked back)" if "clarify" in seen else ""
        flag = "OK  " if ok and fast else ("SLOW" if ok else "FAIL")
        print(f"  {flag} {what:17} {secs:5.1f} s{clarify}", flush=True)
    print("\nReady for the demo." if not bad and ready else f"\n{bad} check(s) failed or were slow.")
    return 0 if not bad and ready else 1


if __name__ == "__main__":
    sys.exit(main())
