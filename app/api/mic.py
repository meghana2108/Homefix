"""WS /api/mic: live transcript while the user speaks (P2).

Client: binary audio chunks (MediaRecorder webm/opus, every 3 s), then text {"type":"stop"}.
Server: chunks are appended to one file per connection; after each chunk the whole file is
converted to 16 kHz WAV and transcribed with models.whisper_live -> {"type":"partial","text":...}.
On stop, one pass with models.whisper_file -> {"type":"final","text":...,"speech":bool}, then the socket
closes. speech is the audio pipeline's own test (is_speech: >= 3 words and a low no-speech probability).
When it's False (an alarm, a beep, a drip) text is "" and the UI attaches the recording as a sound to name.
A missing Whisper model -> {"type":"error","message":...}. The UI only puts the final text in the
text box; sending it is the user's choice, and the safety filter runs then, as for typed text.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

from app.contracts import ModelUnavailable
from app.models.whisper import TranscriptResult, transcribe
from app.pipelines.audio import is_speech

router = APIRouter()
MAX_BYTES = 20 * 1024 * 1024    # opus at ~32 kbit/s: well over an hour; stops a runaway client
FFMPEG_TIMEOUT_S = 30


def _to_wav(src: Path, dst: Path) -> bool:
    """Convert the recording so far to 16 kHz mono WAV. False when it can't be decoded yet."""
    if not src.is_file() or src.stat().st_size == 0:
        return False
    try:
        p = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-vn", "-ac", "1",
                            "-ar", "16000", "-c:a", "pcm_s16le", str(dst)],
                           capture_output=True, check=False, timeout=FFMPEG_TIMEOUT_S)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
    return p.returncode == 0 and dst.is_file() and dst.stat().st_size > 0


def _text(rec: Path, wav: Path, repo: str) -> str | None:
    """Transcript of the whole recording so far, or None if it can't be decoded yet."""
    tr = _transcript(rec, wav, repo)
    return tr.text if tr is not None else None


def _transcript(rec: Path, wav: Path, repo: str) -> TranscriptResult | None:
    if not _to_wav(rec, wav):
        return None
    return transcribe(wav, repo)


@router.websocket("/api/mic")
async def mic(ws: WebSocket) -> None:
    from app.api.main import get_ctx

    await ws.accept()
    profile = get_ctx(ws).profile
    models, max_no_speech = profile.models, profile.audio.speech_max_no_speech_prob
    tmp = Path(tempfile.mkdtemp(prefix="homefix_mic_"))
    rec, wav = tmp / "recording.webm", tmp / "recording.wav"
    size, last = 0, ""

    async def finish() -> None:
        text, speech = last, bool(last.strip())
        if size:
            tr = await run_in_threadpool(_transcript, rec, wav, models.whisper_file)
            if tr is not None:
                speech = is_speech("none", tr, max_no_speech)
                text = tr.text.strip() if speech else ""
        await ws.send_json({"type": "final", "text": text, "speech": speech})

    try:
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                return
            data = msg.get("bytes")
            if data is not None:
                size += len(data)
                with rec.open("ab") as f:
                    f.write(data)
                if size > MAX_BYTES:
                    await finish()
                    break
                text = await run_in_threadpool(_text, rec, wav, models.whisper_live)
                last = text if text is not None else last
                await ws.send_json({"type": "partial", "text": last})
                continue
            try:
                cmd = json.loads(msg.get("text") or "")
            except ValueError:
                continue
            if isinstance(cmd, dict) and cmd.get("type") == "stop":
                await finish()
                break
    except ModelUnavailable as e:
        await ws.send_json({"type": "error", "message": str(e)})
    except WebSocketDisconnect:
        return
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    await ws.close()
