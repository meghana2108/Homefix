"""Mock server: every scenario follows the contract, so the UI can be built before the backend."""

import pytest
import yaml
from fastapi.testclient import TestClient

from app.contracts import EVENT_TYPES, Final
from app.settings import ROOT
from mock_server import scripts, server

SAFETY_TEXT = yaml.safe_load((ROOT / "config/safety_rules.yaml").read_text())["message"]


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(server, "DELAY_SCALE", 0.0)
    return TestClient(server.app)


@pytest.mark.parametrize("name", sorted(scripts.SCENARIOS))
def test_every_scenario_ends_with_final(name):
    steps = scripts.SCENARIOS[name]("hello", ["x.jpg"], None)
    events = [ev for _, ev in steps]
    assert isinstance(events[-1], Final)
    assert sum(isinstance(ev, Final) for ev in events) == 1
    assert all(0.1 <= delay <= 1.5 for delay, _ in steps)


def test_final_latency_is_sum_of_delays():
    steps = scripts.script_for("how many mugs", ["mugs.jpg"], None)
    assert steps[-1][1].latency_ms == round(sum(d for d, _ in steps) * 1000)
    assert steps[-1][1].profile == "full"


def test_all_event_types_covered():
    seen = {ev.type for fn in scripts.SCENARIOS.values() for _, ev in fn("hello", ["x.exe"], None)}
    assert seen == set(EVENT_TYPES)


@pytest.mark.parametrize(("message", "files", "manual", "first_type", "last_before_final"), [
    ("I smell gas", [], None, "status", "refusal"),
    ("", ["setup.exe"], None, "status", "refusal"),
    ("", [], None, "status", "refusal"),
    ("crash please", [], None, "status", "error"),
    ("write a failing function", [], None, "status", "code_result"),
    ("write a function", [], None, "status", "code_result"),
    ("", ["fridge.csv"], None, "status", "code_result"),
    ("what did she say", ["note.m4a"], None, "status", "token"),
    ("what is this", ["beep.wav"], None, "status", "sound_labels"),
    ("what happens", ["drum.mp4"], None, "status", "token"),
    ("is the warranty not in here", ["manual.pdf"], None, "status", "refusal"),
    ("when do I clean the filter", [], "washer_manual", "status", "citation"),
    ("how many mugs", ["mugs.jpg"], None, "status", "token"),
    ("how do I unclog a drain", [], None, "status", "refusal"),
])
def test_script_picks_scenario(message, files, manual, first_type, last_before_final):
    events = [ev for _, ev in scripts.script_for(message, files, manual)]
    assert events[0].type == first_type
    assert events[-2].type == last_before_final
    assert events[-1].type == "final"


@pytest.mark.parametrize(("message", "category"), [
    ("I smell gas", "gas"), ("something is burning", "smoke_fire"), ("sparks from the plug", "sparks"),
])
def test_safety_categories(message, category):
    refusal = scripts.script_for(message, [], None)[-2][1]
    assert refusal.reason == "safety"
    assert refusal.category == category
    assert refusal.message == SAFETY_TEXT


def test_failing_code_result():
    result = scripts.script_for("write a failing function", [], None)[-2][1]
    assert (result.passed, result.failures, result.tests_run) == (False, 1, 3)


def test_passing_code_shows_swap_time():
    events = [ev for _, ev in scripts.script_for("write a function", [], None)]
    loading = [ev for ev in events if ev.type == "status" and ev.stage == "loading_model"]
    assert loading and loading[0].ms == 6400
    assert any(ev.type == "status" and ev.stage == "running_code" for ev in events)
    assert events[-2].passed is True and events[-2].tests_run == 2


@pytest.mark.parametrize(("code", "failed"), [(scripts.PASSING_CODE, 0), (scripts.FAILING_CODE, 1)])
def test_canned_code_really_runs(tmp_path, code, failed):
    """The canned code panel must not claim 'passed' for code that doesn't pass."""
    import doctest
    import importlib.util

    (tmp_path / "solution.py").write_text(code)
    spec = importlib.util.spec_from_file_location("solution", tmp_path / "solution.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    result = doctest.testmod(mod)
    assert result.failed == failed and result.attempted >= 2


def test_sound_labels_values():
    labels = scripts.script_for("", ["beep.wav"], None)[-2][1].labels
    assert [(lb.label, lb.score) for lb in labels] == [
        ("washing machine beeping", 0.71), ("beep", 0.12), ("alarm", 0.05)]


def test_video_frames():
    frames = next(ev for _, ev in scripts.script_for("", ["drum.mov"], None) if ev.type == "frames")
    assert len(frames.timestamps) == 16
    assert frames.timestamps[0] == 0.0 and frames.timestamps[-1] == 28.1


def test_image_answer_streams():
    events = [ev for _, ev in scripts.script_for("how many mugs", ["mugs.jpg"], None)]
    tokens = "".join(ev.text for ev in events if ev.type == "token")
    assert tokens == "4. Four mugs on the shelf."
    assert events[-1].answer == tokens


def test_citation():
    cit = next(ev for _, ev in scripts.script_for("filter?", [], "washer_manual") if ev.type == "citation")
    assert (cit.page, cit.source) == (12, "washer_manual.pdf")


def test_sse_endpoint(client):
    r = client.post("/api/chat", data={"message": "I smell gas"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    assert "event: refusal" in r.text
    assert SAFETY_TEXT.split("\n")[0][:40] in r.text
    assert r.text.rstrip().rsplit("event: ", 1)[1].startswith("final")


def test_unsupported_message(client):
    r = client.post("/api/chat", data={"message": ""}, files=[("files", ("setup.exe", b"x"))])
    assert "I can't open .exe files. Try a photo, audio, video, PDF, Word, text or CSV file." in r.text


def test_empty_post(client):
    r = client.post("/api/chat", data={"message": ""})
    assert "Type a question or attach a file." in r.text


def test_health_and_manuals(client):
    assert set(client.get("/api/health").json()) == {"profile", "ollama", "models", "loaded"}
    assert client.get("/api/manuals").json() == [
        {"id": "washer_manual", "title": "washer_manual.pdf", "pages": 64}]


def test_cors_allows_vite(client):
    r = client.options("/api/chat", headers={"Origin": "http://localhost:5173",
                                             "Access-Control-Request-Method": "POST"})
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_mic_websocket(client):
    with client.websocket_connect("/api/mic") as ws:
        ws.send_bytes(b"chunk1")
        assert ws.receive_json() == {"type": "partial", "text": "testing"}
        ws.send_bytes(b"chunk2")
        assert ws.receive_json() == {"type": "partial", "text": "testing"}
        ws.send_json({"type": "stop"})
        assert ws.receive_json() == {"type": "final", "text": "testing one two"}
