"""The real-samples fetcher's pinned list: free licenses, clean names, the demo's five files. No network."""

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("fetch_real_samples", ROOT / "scripts" / "fetch_real_samples.py")
f = importlib.util.module_from_spec(_spec)
sys.modules["fetch_real_samples"] = f
_spec.loader.exec_module(f)


def test_demo_media_listed():
    assert f.DEMO_MEDIA == ("real_breaker_panel.jpg", "real_leaking_pipe.jpg", "real_thermostat_66.jpg",
                            "real_smoke_detector.jpg", "real_smoke_alarm_chirp.wav")
    assert all(n in f.names() for n in f.DEMO_MEDIA)


def test_chirp_is_a_sound():
    c = next(x for x in f.COMMONS if x.out == "real_smoke_alarm_chirp.wav")
    assert c.kind == "sound"
    assert c.seconds <= 10
    assert (c.start, c.seconds, c.gain_db) == (38.0, 9.0, 20.0)  # the window HomeFix hears as a smoke-alarm chirp


def test_pinned_list_is_clean():
    assert f.check_list(f.COMMONS) == []


def test_check_list_rejects_non_free():
    bad = f.Commons("real_x.jpg", "X.jpg", "photo", "me", "CC BY-NC 2.0")
    problems = f.check_list([bad])
    assert len(problems) == 1 and "real_x.jpg" in problems[0]


def test_check_list_rejects_duplicates_and_bad_names():
    ok = f.Commons("real_a.jpg", "A.jpg", "photo", "me", "CC0")
    assert f.check_list([ok, ok])
    assert f.check_list([f.Commons("../x.jpg", "X.jpg", "photo", "me", "CC0")])
    assert f.check_list([f.Commons("a.jpg", "X.webm", "sound", "me", "CC0")])


def test_samples_folder_ignored():
    r = subprocess.run(["git", "check-ignore", "frontend/public/samples/real_x.jpg"], check=False, cwd=ROOT)
    assert r.returncode == 0
