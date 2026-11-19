"""HTTP API: /api/chat streams SSE events from handle(); health and manuals for the UI."""

import time

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.contracts import Status, Token, final_for
from app.models import ollama_client
from app.pipelines import image
from tests import media_fixtures as mf


@pytest.fixture
def client(ctx_full):
    app.state.ctx = ctx_full
    yield TestClient(app)
    del app.state.ctx


def events_of(body: str) -> list[str]:
    return [ln.split(":", 1)[1].strip() for ln in body.splitlines() if ln.startswith("event:")]


def test_chat_streams_sse(client):
    r = client.post("/api/chat", data={"message": ""})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    assert events_of(r.text)[-2:] == ["refusal", "final"]
    assert "Type a question or attach a file." in r.text


def test_safety_over_http(client):
    r = client.post("/api/chat", data={"message": "I smell gas"})
    assert events_of(r.text)[-2:] == ["refusal", "final"] and '"category":"gas"' in r.text


def test_upload_goes_through_and_is_deleted(client, tmp_path, monkeypatch):
    seen = []

    def run(req, ctx):
        seen.append(req.attachments[0])
        yield Status(stage="generating")
        yield Token(text="4.")
        yield final_for(ctx, "image", req.question_type, "4.")
    monkeypatch.setattr(image, "run", run)
    jpg = mf.make_jpeg(tmp_path / "mugs.jpg").read_bytes()
    r = client.post("/api/chat", data={"message": "how many mugs"},
                    files=[("files", ("../../etc/mugs.jpg", jpg, "image/jpeg"))])
    assert events_of(r.text) == ["status", "status", "status", "status", "token", "final"]
    assert '"modality":"image"' in r.text and '"question_type":"count"' in r.text
    assert seen[0].original_name == "mugs.jpg"  # path parts stripped from the upload name
    assert not seen[0].path.exists() and not seen[0].path.parent.exists()


def test_unsupported_upload(client):
    r = client.post("/api/chat", data={"message": ""}, files=[("files", ("setup.exe", b"MZ"))])
    assert "I can't open .exe files. Try a photo, audio, video, PDF, Word, text or CSV file." in r.text


def test_too_many_uploads(client):
    files = [("files", (f"{i}.txt", b"x")) for i in range(5)]
    assert "Attach up to 4 files at a time." in client.post("/api/chat", data={"message": "q"}, files=files).text


def test_oversize_upload_stops_early(client, monkeypatch, ctx_full):
    monkeypatch.setattr(ctx_full.profile.server, "max_file_mb", 1)
    big = b"x" * (3 * 1024 * 1024)
    r = client.post("/api/chat", data={"message": "q"}, files=[("files", ("big.txt", big))])
    assert "That file is over 200 MB." in r.text


def test_manual_id_passed(client, monkeypatch):
    from app.pipelines import text
    seen = []
    monkeypatch.setattr(text, "run", lambda req, ctx: (seen.append(req.manual_id), iter([]))[1])
    client.post("/api/chat", data={"message": "When do I clean the filter?", "manual_id": "washer_lg"})
    assert seen == ["washer_lg"]


def test_health_shape(client, monkeypatch):
    monkeypatch.setattr(ollama_client, "is_up", lambda: False)
    body = client.get("/api/health").json()
    assert set(body) == {"profile", "ollama", "models", "loaded"}
    assert body["profile"] == "full" and body["ollama"] is False and body["loaded"] == []
    assert body["models"]["brain"] == "qwen3-vl:8b"


def test_health_fast_when_ollama_down(client, monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:9")
    t0 = time.perf_counter()
    assert client.get("/api/health").json()["ollama"] is False
    assert time.perf_counter() - t0 < 2.5


def test_health_lists_loaded(client, monkeypatch, ctx_full):
    monkeypatch.setattr(ollama_client, "is_up", lambda: True)
    assert client.get("/api/health").json()["loaded"] == ctx_full.memory.backend.loaded()


def test_manuals_empty(client):
    assert client.get("/api/manuals").json() == []


def test_cors_allows_vite(client):
    for origin in ("http://localhost:5173", "http://127.0.0.1:5173"):
        r = client.options("/api/chat", headers={"Origin": origin, "Access-Control-Request-Method": "POST"})
        assert r.headers["access-control-allow-origin"] == origin


def test_cors_blocks_others(client):
    r = client.options("/api/chat", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in r.headers


