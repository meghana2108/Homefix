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

import asyncio
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


def _warm(repo: str) -> None:
    """Load Whisper now (half a second of silence), so the first partial doesn't wait ~10 s for it."""
    import numpy as np
    import soundfile as sf

    tmp = Path(tempfile.mkdtemp(prefix="homefix_warm_"))
    try:
        sf.write(tmp / "silence.wav", np.zeros(8000, dtype=np.float32), 16000)
        transcribe(tmp / "silence.wav", repo)
    except Exception:  # noqa: BLE001, S110 - warming is only a speed-up; real errors surface on the real call
        pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@router.websocket("/api/mic")
async def mic(ws: WebSocket) -> None:
    """One live transcript at a time: chunks that arrive while one runs are folded into the next, so stop
    waits for at most one transcript in progress, then the final pass."""
    from app.api.main import get_ctx

    await ws.accept()
    profile = get_ctx(ws).profile
    models, max_no_speech = profile.models, profile.audio.speech_max_no_speech_prob
    tmp = Path(tempfile.mkdtemp(prefix="homefix_mic_"))
    rec, wav = tmp / "recording.webm", tmp / "recording.wav"
    state = {"size": 0, "last": "", "new_audio": False, "failed": False}
    warm = asyncio.ensure_future(run_in_threadpool(_warm, models.whisper_live))
    live: asyncio.Future | None = None

    async def partials() -> None:
        await warm
        try:
            while state["new_audio"] and not state["failed"]:
                state["new_audio"] = False
                text = await run_in_threadpool(_text, rec, wav, models.whisper_live)
                state["last"] = text if text is not None else state["last"]
                await ws.send_json({"type": "partial", "text": state["last"]})
        except ModelUnavailable as e:  # runs beside the receive loop, so it reports the error itself
            state["failed"] = True
            await ws.send_json({"type": "error", "message": str(e)})

    async def finish() -> None:
        state["new_audio"] = False   # the final pass hears everything; no more partials
        if live is not None:
            await live
        await warm
        if state["failed"]:
            return
        text, speech = state["last"], bool(state["last"].strip())
        if state["size"]:
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
                state["size"] += len(data)
                with rec.open("ab") as f:
                    f.write(data)
                if state["size"] > MAX_BYTES:
                    await finish()
                    break
                state["new_audio"] = True
                if live is None or live.done():
                    live = asyncio.ensure_future(partials())
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
        for task in (live, warm):
            if task is not None and not task.done():
                task.cancel()
        shutil.rmtree(tmp, ignore_errors=True)
    await ws.close()
