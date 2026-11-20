"""Live mic over WebSocket: a partial transcript after each chunk, then one final on stop."""

import subprocess

import pytest
from fastapi.testclient import TestClient

from app.api import mic
from app.api.main import app
from app.contracts import MESSAGES, ModelUnavailable
from app.models.whisper import TranscriptResult
from tests import media_fixtures as mf


@pytest.fixture
def warmed(monkeypatch):
    calls = []
    monkeypatch.setattr(mic, "_warm", lambda repo: calls.append(repo))
    return calls


@pytest.fixture
def client(ctx_lite, warmed):
    app.state.ctx = ctx_lite
    yield TestClient(app)
    del app.state.ctx


@pytest.fixture
def fake_asr(monkeypatch):
    """Conversion always works; transcribe returns the next text and records which model ran."""
    calls = []
    texts = ["testing", "testing one two"]  # the last one repeats

    def to_wav(src, dst):
        dst.write_bytes(b"RIFF")
        calls.append(("convert", src.stat().st_size))
        return True

    def transcribe(path, repo):
        calls.append(("transcribe", repo))
        return TranscriptResult(text=texts.pop(0) if len(texts) > 1 else texts[0], seconds=1.0,
                                mean_no_speech_prob=0.1)
    monkeypatch.setattr(mic, "_to_wav", to_wav)
    monkeypatch.setattr(mic, "transcribe", transcribe)
    return calls


def test_partials_then_final(client, fake_asr, ctx_lite):
    with client.websocket_connect("/api/mic") as ws:
        ws.send_bytes(b"chunk1")
        assert ws.receive_json() == {"type": "partial", "text": "testing"}
        ws.send_bytes(b"chunk2")
        # one partial per chunk; the stub returns the 2nd text here, so the final re-runs on the whole file
        ws.receive_json()
        ws.send_json({"type": "stop"})
        final = ws.receive_json()
    assert final["type"] == "final"
    # chunks are appended to one file: the 2nd conversion sees both chunks
    assert [c[1] for c in fake_asr if c[0] == "convert"][:2] == [6, 12]
    repos = [c[1] for c in fake_asr if c[0] == "transcribe"]
    assert repos[:2] == [ctx_lite.profile.models.whisper_live] * 2
    assert repos[-1] == ctx_lite.profile.models.whisper_file


def test_plan_protocol(client, monkeypatch):
    """The plan's test: 2 chunks, stop -> 2 partials, then final 'testing one two'."""
    texts = iter(["testing", "testing", "testing one two"])
    monkeypatch.setattr(mic, "_to_wav", lambda src, dst: dst.write_bytes(b"x") or True)
    monkeypatch.setattr(mic, "transcribe",
                        lambda p, r: TranscriptResult(text=next(texts), seconds=1.0, mean_no_speech_prob=0.1))
    with client.websocket_connect("/api/mic") as ws:
        ws.send_bytes(b"a")
        p1 = ws.receive_json()
        ws.send_bytes(b"b")
        p2 = ws.receive_json()
        ws.send_json({"type": "stop"})
        final = ws.receive_json()
    assert [p1["type"], p2["type"]] == ["partial", "partial"]
    assert final == {"type": "final", "text": "testing one two", "speech": True}


def test_unreadable_chunk_keeps_last_partial(client, monkeypatch):
    """The first chunk of a recording can be too short to decode; send what we have, don't fail."""
    monkeypatch.setattr(mic, "_to_wav", lambda src, dst: False)
    monkeypatch.setattr(mic, "transcribe", lambda p, r: pytest.fail("no audio to transcribe"))
    with client.websocket_connect("/api/mic") as ws:
        ws.send_bytes(b"x")
        assert ws.receive_json() == {"type": "partial", "text": ""}
        ws.send_json({"type": "stop"})
        assert ws.receive_json() == {"type": "final", "text": "", "speech": False}


def test_stop_without_audio(client, fake_asr):
    with client.websocket_connect("/api/mic") as ws:
        ws.send_json({"type": "stop"})
        assert ws.receive_json() == {"type": "final", "text": "", "speech": False}
    assert fake_asr == []


def test_whisper_missing_is_an_error_message(client, monkeypatch):
    monkeypatch.setattr(mic, "_to_wav", lambda src, dst: dst.write_bytes(b"x") or True)

    def boom(p, r):
        raise ModelUnavailable(MESSAGES["model_missing"].format(role="whisper"))
    monkeypatch.setattr(mic, "transcribe", boom)
    with client.websocket_connect("/api/mic") as ws:
        ws.send_bytes(b"x")
        assert ws.receive_json() == {"type": "error",
                                     "message": "The whisper model isn't installed. Run scripts/pull_models.sh."}


def test_too_long_recording_stops(client, fake_asr, monkeypatch):
    monkeypatch.setattr(mic, "MAX_BYTES", 10)
    with client.websocket_connect("/api/mic") as ws:
        ws.send_bytes(b"0123456789AB")
        msg = ws.receive_json()
    assert msg["type"] == "final"


def test_bad_text_message_is_ignored(client, fake_asr):
    with client.websocket_connect("/api/mic") as ws:
        ws.send_text("not json")
        ws.send_json({"type": "stop"})
        assert ws.receive_json()["type"] == "final"


def test_temp_folder_removed(client, fake_asr, monkeypatch):
    seen = []
    real = mic.tempfile.mkdtemp
    monkeypatch.setattr(mic.tempfile, "mkdtemp", lambda **kw: seen.append(real(**kw)) or seen[-1])
    with client.websocket_connect("/api/mic") as ws:
        ws.send_bytes(b"x")
        ws.receive_json()
        ws.send_json({"type": "stop"})
        ws.receive_json()
    from pathlib import Path
    assert seen and not Path(seen[0]).exists()


def test_real_conversion_of_webm_chunks(tmp_path):
    """Chunks of a webm/opus stream, joined, convert to 16 kHz mono WAV (what MediaRecorder sends)."""
    mf.need_ffmpeg()
    webm = mf.make_webm_audio_only(tmp_path / "rec.webm")
    data = webm.read_bytes()
    joined = tmp_path / "joined.webm"
    joined.write_bytes(data[: len(data) // 2] + data[len(data) // 2:])
    out = tmp_path / "out.wav"
    assert mic._to_wav(joined, out) is True
    info = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=sample_rate,channels", "-of",
                           "csv=p=0", str(out)], capture_output=True, text=True, check=True).stdout.strip()
    assert info == "16000,1"
    assert mic._to_wav(tmp_path / "missing.webm", out) is False


def test_a_sound_is_not_speech_so_no_words_go_in_the_box(client, monkeypatch):
    """An alarm: Whisper hears "beep beep beep beep" with a high no-speech probability (measured 0.82 on our
    chirp). The final says speech=False and carries no text; the UI attaches the recording instead."""
    monkeypatch.setattr(mic, "_to_wav", lambda src, dst: dst.write_bytes(b"RIFF") or True)
    monkeypatch.setattr(mic, "transcribe", lambda path, repo: TranscriptResult(
        text="beep beep beep beep", seconds=4.0, mean_no_speech_prob=0.82))
    with client.websocket_connect("/api/mic") as ws:
        ws.send_bytes(b"chunk1")
        ws.receive_json()
        ws.send_json({"type": "stop"})
        assert ws.receive_json() == {"type": "final", "text": "", "speech": False}


def test_silence_is_not_speech(client, monkeypatch):
    monkeypatch.setattr(mic, "_to_wav", lambda src, dst: dst.write_bytes(b"RIFF") or True)
    monkeypatch.setattr(mic, "transcribe", lambda path, repo: TranscriptResult(text="", seconds=2.0,
                                                                              mean_no_speech_prob=1.0))
    with client.websocket_connect("/api/mic") as ws:
        ws.send_bytes(b"chunk1")
        ws.receive_json()
        ws.send_json({"type": "stop"})
        assert ws.receive_json() == {"type": "final", "text": "", "speech": False}


def test_whisper_starts_loading_when_the_mic_opens(client, warmed, fake_asr, ctx_lite):
    """The first transcript used to wait ~10 s for Whisper to load, and every chunk queued behind it."""
    with client.websocket_connect("/api/mic") as ws:
        ws.send_json({"type": "stop"})
        ws.receive_json()
    assert warmed == [ctx_lite.profile.models.whisper_live]


def test_chunks_that_arrive_during_a_transcript_are_folded_into_the_next_one(client, monkeypatch, ctx_lite):
    """Stop waits for at most one transcript in progress, not one per chunk; the final hears every chunk."""
    import threading
    gate = threading.Event()
    seen = []

    def to_wav(src, dst):
        dst.write_bytes(b"RIFF")
        seen.append(src.stat().st_size)
        return True

    def transcribe(path, repo):
        gate.wait(5)
        return TranscriptResult(text="beep", seconds=1.0, mean_no_speech_prob=0.9)
    monkeypatch.setattr(mic, "_to_wav", to_wav)
    monkeypatch.setattr(mic, "transcribe", transcribe)
    with client.websocket_connect("/api/mic") as ws:
        ws.send_bytes(b"aa")        # transcript 1 starts and blocks
        ws.send_bytes(b"bb")        # arrive while it runs
        ws.send_bytes(b"cc")
        ws.send_json({"type": "stop"})
        gate.set()
        msgs = []
        while True:
            m = ws.receive_json()
            msgs.append(m)
            if m["type"] == "final":
                break
    assert msgs[-1] == {"type": "final", "text": "", "speech": False}
    assert len(seen) <= 2          # one live transcript, then the final, instead of 3 + 1
    assert seen[-1] == 6           # the final covers all three chunks
