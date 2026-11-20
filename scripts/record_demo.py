"""Record the demo's six answers from the running backend, for the #/demo page to replay.

    uv run python scripts/record_demo.py [--base-url http://127.0.0.1:8000] [--scene photo ...]

Needs the backend running on the full profile. A scene is written to
frontend/src/demo/recordings/<scene>.json only if its answer passes the checks below;
a failed scene prints why and leaves the old file alone.
Exit code: 0 all passed, 1 a scene failed, 2 the backend is not on the full profile.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
RECORDINGS = Path("frontend/src/demo/recordings")
CHAT_TIMEOUT_S = 180
MAX_STRING = 4000
MANUAL = "apartment_guide_unit_4b"


@dataclass(frozen=True)
class SceneInput:
    message: str
    disk_file: str | None
    web_file: str | None
    manual_id: str | None


SCENES: dict[str, SceneInput] = {
    "photo": SceneInput("What should I do?", "frontend/public/samples/washer_display_e21.jpg",
                        "/samples/washer_display_e21.jpg", MANUAL),
    "sound": SceneInput("What is this sound?", "frontend/public/samples/real_smoke_alarm_chirp.wav",
                        "/samples/real_smoke_alarm_chirp.wav", None),
    "video": SceneInput("How many warning lights are on at the end?", "frontend/public/samples/warning_lights.mp4",
                        "/samples/warning_lights.mp4", None),
    "honesty": SceneInput("Is there a warranty on the washer?", None, None, MANUAL),
    "danger": SceneInput("I smell burning from the outlet behind the fridge", None, None, None),
    "code": SceneInput("Write a function that converts a thermostat temperature from Fahrenheit to Celsius.",
                       None, None, None),
}

SETUP_SCRIPT = {
    ".jpg": "scripts/make_samples.py",
    ".wav": "scripts/fetch_real_samples.py",
    ".mp4": "scripts/make_samples.py",
}
VIDEO_LIGHTS = 4  # warning_lights.mp4 ends with four lights on (scripts/make_samples.py lights_clip)


class SceneFailed(Exception):
    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


def parse_sse(text: str) -> list[dict]:
    """Event dicts from an SSE body. Reads `data:` lines; ignores event/id/retry/comment lines."""
    events: list[dict] = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if not line.startswith("data:"):
            continue
        payload = line[5:].removeprefix(" ")
        try:
            events.append(json.loads(payload))
        except json.JSONDecodeError as e:
            raise ValueError(f"bad event: {payload[:80]!r} ({e})") from e
    return events


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)


def check_no_inline_media(events: list[dict]) -> list[str]:
    problems = []
    for s in _strings(events):
        if s.startswith("data:"):
            problems.append(f"inline media in a recorded string: {s[:30]!r}")
        elif len(s) > MAX_STRING:
            problems.append(f"a recorded string is {len(s)} characters (limit {MAX_STRING})")
    return problems


def check_scene(scene: str, events: list[dict]) -> list[str]:
    """Problems that make this answer unfit for the demo. An empty list means pass."""
    problems = []
    by_type = lambda t: [e for e in events if e.get("type") == t]
    refusals = by_type("refusal")
    if not by_type("final"):
        problems.append("no final event")
    for err in by_type("error"):
        problems.append(f"error event: {err.get('message', '')}")

    if scene == "photo":
        for r in refusals:
            problems.append(f"unexpected refusal ({r.get('reason')})")
        if not any("e21" in str(c.get("quote", "")).lower() for c in by_type("citation")):
            problems.append("no citation quote containing E21")
    elif scene == "sound":
        for r in refusals:
            problems.append(f"unexpected refusal ({r.get('reason')})")
        sl = by_type("sound_labels")
        top = sl[0]["labels"][0]["label"] if sl and sl[0].get("labels") else None
        if top != "smoke alarm chirp":
            problems.append(f"top sound label is {top!r}, expected 'smoke alarm chirp'")
    elif scene == "video":
        for r in refusals:
            problems.append(f"unexpected refusal ({r.get('reason')})")
        if not by_type("frames"):
            problems.append("no frames event")
        answer = str((by_type("final") or [{}])[0].get("answer") or "")
        m = re.search(r"\d+", answer)
        if not m or int(m.group()) != VIDEO_LIGHTS:
            problems.append(f"answer {answer[:40]!r} does not start with the count; expected {VIDEO_LIGHTS}")
    elif scene == "code":
        for r in refusals:
            problems.append(f"unexpected refusal ({r.get('reason')})")
        results = by_type("code_result")
        if not results:
            problems.append("no code_result event")
        else:
            r = results[-1]
            if not r.get("tests_run"):
                problems.append("no examples ran in the sandbox")
            elif not r.get("passed"):
                problems.append(f"the code did not pass its examples ({r.get('failures')} of {r.get('tests_run')} failed)")
    elif scene in ("honesty", "danger"):
        want = "not_in_document" if scene == "honesty" else "safety"
        if not any(r.get("reason") == want for r in refusals):
            got = [r.get("reason") for r in refusals] or "none"
            problems.append(f"expected refusal reason {want!r}, got {got}")
    else:
        problems.append(f"unknown scene {scene!r}")
    return problems


def record_scene(scene: str, client: httpx.Client, root: Path) -> dict:
    """Send the scene's request, check the answer, return the recording. Raises SceneFailed."""
    inp = SCENES[scene]
    data = {"message": inp.message}
    if inp.manual_id:
        data["manual_id"] = inp.manual_id
    files = None
    handle = None
    if inp.disk_file:
        path = root / inp.disk_file
        if not path.is_file():
            hint = SETUP_SCRIPT.get(path.suffix, "the sample setup scripts")
            raise SceneFailed([f"missing input file {inp.disk_file}; run uv run python {hint}"])
        handle = path.open("rb")
        files = [("files", (path.name, handle))]
    try:
        resp = client.post("/api/chat", data=data, files=files, timeout=CHAT_TIMEOUT_S)
        resp.raise_for_status()
        events = parse_sse(resp.text)
    except httpx.TimeoutException as e:
        raise SceneFailed([f"request timed out after {CHAT_TIMEOUT_S} s ({type(e).__name__})"]) from e
    except httpx.HTTPError as e:
        raise SceneFailed([f"request failed: {e}"]) from e
    except ValueError as e:
        raise SceneFailed([str(e)]) from e
    finally:
        if handle:
            handle.close()
    problems = check_scene(scene, events) + check_no_inline_media(events)
    if problems:
        raise SceneFailed(problems)
    return {
        "scene": scene,
        "recorded_at": datetime.now().isoformat(timespec="seconds"),
        "profile": "full",
        "request": {"message": inp.message, "files": [inp.web_file] if inp.web_file else [],
                    "manual_id": inp.manual_id},
        "events": events,
    }


def _write_atomic(path: Path, rec: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(rec, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def main(argv: list[str] | None = None, client: httpx.Client | None = None, root: Path = ROOT) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--scene", action="append", choices=list(SCENES), help="repeatable; default all six")
    args = ap.parse_args(argv)
    scenes = args.scene or list(SCENES)
    client = client or httpx.Client(base_url=args.base_url)

    try:
        profile = client.get("/api/health", timeout=10).json().get("profile")
    except (httpx.HTTPError, ValueError) as e:
        print(f"cannot reach the backend: {e}")
        return 2
    if profile != "full":
        print(f"backend profile is {profile!r}; the demo is recorded on 'full'. Nothing written.")
        return 2

    failed = 0
    for scene in scenes:
        try:
            rec = record_scene(scene, client, root)
            _write_atomic(root / RECORDINGS / f"{scene}.json", rec)
            print(f"{scene}: ok")
        except SceneFailed as e:
            failed += 1
            print(f"{scene}: FAILED - {'; '.join(e.problems)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
