"""The demo recorder, run against a mocked backend (never the live server)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from urllib.parse import unquote_plus

import httpx
import pytest

from app.contracts import Citation, Final, Refusal, SoundLabel, SoundLabels, Status, to_sse

_spec = importlib.util.spec_from_file_location(
    "record_demo", Path(__file__).resolve().parents[1] / "scripts" / "record_demo.py")
rd = importlib.util.module_from_spec(_spec)
sys.modules["record_demo"] = rd
_spec.loader.exec_module(rd)

REC = Path("frontend/src/demo/recordings")


def wire(events) -> str:
    """The body sse-starlette sends: event/data lines, CRLF, blank line after each."""
    out = ""
    for e in events:
        d = to_sse(e)
        out += f"event: {d['event']}\r\ndata: {d['data']}\r\n\r\n"
    return out


FINAL = Final(answer="ok", modality="none", question_type="none", profile="full")
SAFETY = Refusal(reason="safety", message="Stop. Leave and call 911.", category="sparks")
NOT_IN = Refusal(reason="not_in_document", message="The document doesn't contain the answer.")

GOOD = {
    "photo": [Status(stage="generating"),
              Citation(quote="E21 Drain fault ...", page=3, source="guide.pdf", score=97.0), FINAL],
    "sound": [SoundLabels(labels=[SoundLabel(label="smoke alarm chirp", score=0.9)], is_speech=False), FINAL],
    "honesty": [NOT_IN, FINAL],
    "danger": [SAFETY, FINAL],
}


def dicts(events) -> list[dict]:
    return rd.parse_sse(wire(events))


def make_root(tmp_path: Path, jpg=True, wav=True) -> Path:
    s = tmp_path / "frontend/public/samples"
    s.mkdir(parents=True)
    if jpg:
        (s / "washer_display_e21.jpg").write_bytes(b"\xff\xd8stub")
    if wav:
        (s / "real_smoke_alarm_chirp.wav").write_bytes(b"RIFFstub")
    return tmp_path


def client(bodies: dict[str, str | Exception], profile="full", seen=None) -> httpx.Client:
    """bodies maps the message text to an SSE body (or an exception to raise)."""
    def handler(req: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(req)
        if req.url.path == "/api/health":
            return httpx.Response(200, json={"profile": profile})
        assert req.url.path == "/api/chat"
        text = unquote_plus(req.read().decode("latin-1"))
        for msg, body in bodies.items():
            if msg in text:
                if isinstance(body, Exception):
                    raise body
                return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})
        raise AssertionError("unexpected chat request")
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test")


MSG = {s: rd.SCENES[s].message for s in rd.SCENES}


def good_bodies() -> dict:
    return {MSG[s]: wire(ev) for s, ev in GOOD.items()}


def test_wrong_profile_exits_2_and_writes_nothing(tmp_path):
    root = make_root(tmp_path)
    seen: list = []
    assert rd.main([], client=client(good_bodies(), profile="lite", seen=seen), root=root) == 2
    assert [r.url.path for r in seen] == ["/api/health"]
    assert not (root / REC).exists() or list((root / REC).iterdir()) == []


def test_all_scenes_pass_and_write(tmp_path):
    root = make_root(tmp_path)
    assert rd.main([], client=client(good_bodies()), root=root) == 0
    for s in GOOD:
        rec = json.loads((root / REC / f"{s}.json").read_text())
        assert list(rec) == ["scene", "recorded_at", "profile", "request", "events"]
        assert rec["scene"] == s and rec["profile"] == "full"


def test_photo_passes_with_e21_quote():
    assert rd.check_scene("photo", dicts(GOOD["photo"])) == []


def test_photo_fails_on_refusal():
    ev = dicts(GOOD["photo"][:2] + [SAFETY, FINAL])
    assert any("refusal" in p for p in rd.check_scene("photo", ev))


def test_photo_fails_when_quote_lacks_code():
    ev = dicts([Citation(quote="Clean the filter", page=1, source="g.pdf", score=95.0), FINAL])
    assert any("E21" in p for p in rd.check_scene("photo", ev))


def test_sound_fails_when_heard_as_alarm():
    ev = dicts([SoundLabels(labels=[SoundLabel(label="smoke detector, smoke alarm", score=0.9)],
                            is_speech=False), FINAL])
    assert any("smoke alarm chirp" in p for p in rd.check_scene("sound", ev))


def test_honesty_needs_not_in_document():
    assert rd.check_scene("honesty", dicts([NOT_IN, FINAL])) == []
    assert rd.check_scene("honesty", dicts([SAFETY, FINAL])) != []


def test_danger_needs_safety():
    assert rd.check_scene("danger", dicts([SAFETY, FINAL])) == []
    assert rd.check_scene("danger", dicts([FINAL])) != []


@pytest.mark.parametrize("scene", list(GOOD))
def test_missing_final_fails(scene):
    ev = dicts([e for e in GOOD[scene] if e.type != "final"])
    assert any("no final" in p for p in rd.check_scene(scene, ev))


def test_model_unavailable_fails():
    ref = Refusal(reason="model_unavailable", message="The local model server isn't running.")
    assert rd.check_scene("photo", dicts([ref, FINAL])) != []


def test_inline_media_flagged():
    assert rd.check_no_inline_media([{"type": "token", "text": "data:image/png;base64,AAAA"}])
    assert rd.check_no_inline_media([{"type": "token", "text": "x" * 4001}])
    assert rd.check_no_inline_media([{"type": "token", "text": "x" * 4000}]) == []
    assert rd.check_no_inline_media([{"a": [{"b": "data:audio/wav;base64,AA"}]}])


def test_parse_sse_ignores_other_lines_and_accepts_lf():
    text = ": ping\nid: 1\nretry: 5\nevent: status\ndata: {\"type\": \"status\", \"stage\": \"routing\"}\n\n"
    assert rd.parse_sse(text) == [{"type": "status", "stage": "routing"}]


def test_bad_sse_line_fails_scene_not_run(tmp_path):
    root = make_root(tmp_path)
    bodies = good_bodies()
    bodies[MSG["photo"]] = "data: {oops\r\n\r\n"
    assert rd.main([], client=client(bodies), root=root) == 1
    assert not (root / REC / "photo.json").exists()
    assert (root / REC / "honesty.json").exists()


def test_failed_scene_keeps_old_recording(tmp_path):
    root = make_root(tmp_path)
    (root / REC).mkdir(parents=True)
    old = b'{"old": true}\n'
    (root / REC / "photo.json").write_bytes(old)
    bodies = good_bodies()
    bodies[MSG["photo"]] = wire([SAFETY, FINAL])
    assert rd.main(["--scene", "photo"], client=client(bodies), root=root) == 1
    assert (root / REC / "photo.json").read_bytes() == old


def test_request_shape(tmp_path):
    root = make_root(tmp_path)
    seen: list = []
    assert rd.main(["--scene", "photo"], client=client(good_bodies(), seen=seen), root=root) == 0
    chat = next(r for r in seen if r.url.path == "/api/chat")
    assert chat.headers["content-type"].startswith("multipart/form-data")
    body = chat.content.decode("latin-1")
    assert 'name="message"\r\n\r\nWhat should I do?' in body
    assert 'name="manual_id"\r\n\r\napartment_guide_unit_4b' in body
    assert body.count('filename="washer_display_e21.jpg"') == 1
    rec = json.loads((root / REC / "photo.json").read_text())
    assert rec["request"] == {"message": "What should I do?", "files": ["/samples/washer_display_e21.jpg"],
                              "manual_id": "apartment_guide_unit_4b"}


def test_no_manual_id_field_for_sound_and_danger(tmp_path):
    root = make_root(tmp_path)
    seen: list = []
    assert rd.main(["--scene", "sound", "--scene", "danger"],
                   client=client(good_bodies(), seen=seen), root=root) == 0
    for r in seen:
        if r.url.path == "/api/chat":
            assert b"manual_id" not in r.content
    assert json.loads((root / REC / "danger.json").read_text())["request"]["files"] == []


def test_missing_input_file_names_setup_script(tmp_path):
    root = make_root(tmp_path, jpg=False, wav=False)
    with pytest.raises(rd.SceneFailed) as e:
        rd.record_scene("photo", client(good_bodies()), root)
    assert any("scripts/make_samples.py" in p for p in e.value.problems)
    with pytest.raises(rd.SceneFailed) as e:
        rd.record_scene("sound", client(good_bodies()), root)
    assert any("scripts/fetch_real_samples.py" in p for p in e.value.problems)


def test_timeout_fails_scene(tmp_path):
    root = make_root(tmp_path)
    bodies = good_bodies()
    bodies[MSG["photo"]] = httpx.ReadTimeout("slow")
    assert rd.main([], client=client(bodies), root=root) == 1
    assert not (root / REC / "photo.json").exists()
    assert (root / REC / "sound.json").exists()
