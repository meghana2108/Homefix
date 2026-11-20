"""Load every resident model when the API starts, in the background, so the first question isn't cold.

Each step loads one model the way the real request path does (same tag, keep_alive and num_ctx for Ollama, the
same repo for Whisper and CLAP), so nothing reloads later. /api/health reports progress as `warm`, and the app
shows "Getting ready" until every step is done. A failed step is reported, not retried: the real request still
loads (or reports) that model. HOMEFIX_WARMUP=off turns it off (tests).
"""

from __future__ import annotations

import os
import shutil
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path

from app.contracts import Ctx

Step = tuple[str, str, Callable[[Ctx], None]]
_state: dict[str, dict] = {}
_order: list[tuple[str, str]] = []
_lock = threading.Lock()


def _silence() -> Path:
    import numpy as np
    import soundfile as sf

    d = Path(tempfile.mkdtemp(prefix="homefix_warm_"))
    sf.write(d / "silence.wav", np.zeros(16000, dtype=np.float32), 16000)
    return d / "silence.wav"


def _brain(ctx: Ctx) -> None:
    for _ in ctx.memory.ensure("brain"):
        pass


def _whisper(repo_of: Callable[[Ctx], str]) -> Callable[[Ctx], None]:
    def fn(ctx: Ctx) -> None:
        from app.models.whisper import transcribe

        wav = _silence()
        try:
            transcribe(wav, repo_of(ctx))
        finally:
            shutil.rmtree(wav.parent, ignore_errors=True)
    return fn


def _clap(ctx: Ctx) -> None:
    from app.models.clap import classify, load_vocab

    wav = _silence()
    try:
        classify(wav, ctx.profile.models.clap, load_vocab(), top_k=1)  # also embeds every label once
    finally:
        shutil.rmtree(wav.parent, ignore_errors=True)


def _embeddings(ctx: Ctx) -> None:
    from app import intent, safety_semantic

    safety_semantic.scores("warm up")
    intent.lean("warm up", "problem", "question")


def steps(ctx: Ctx) -> list[Step]:
    """(name, what the app calls it, load function), in the order a demo needs them."""
    return [
        ("brain", "Vision model", _brain),
        ("whisper_file", "Speech", _whisper(lambda c: c.profile.models.whisper_file)),
        ("whisper_live", "Live mic", _whisper(lambda c: c.profile.models.whisper_live)),
        ("clap", "Sounds", _clap),
        ("embeddings", "Danger check", _embeddings),
    ]


def reset() -> None:
    with _lock:
        _state.clear()
        _order.clear()


def _list(todo: list[Step]) -> None:
    with _lock:
        _order[:] = [(name, label) for name, label, _ in todo]
        for name, _, _ in todo:
            _state[name] = {"state": "waiting", "ms": None}


def run(ctx: Ctx, todo: list[Step] | None = None) -> None:
    todo = steps(ctx) if todo is None else todo
    _list(todo)
    for name, _, fn in todo:
        with _lock:
            _state[name] = {"state": "loading", "ms": None}
        t0 = time.perf_counter()
        try:
            fn(ctx)
            result = "ready"
        except Exception:  # noqa: BLE001 - reported in /api/health; the real request reports the error
            result = "failed"
        with _lock:
            _state[name] = {"state": result, "ms": int((time.perf_counter() - t0) * 1000)}


def start(ctx: Ctx) -> threading.Thread | None:
    if os.environ.get("HOMEFIX_WARMUP") == "off":
        return None
    todo = steps(ctx)
    _list(todo)  # listed before the thread starts, so /api/health never shows an empty, "ready" warm-up
    t = threading.Thread(target=run, args=(ctx, todo), name="warmup", daemon=True)
    t.start()
    return t


def status() -> dict:
    """{"ready": every step ready, "done": no step left to run, "steps": [{name, label, state, ms}]}."""
    with _lock:
        rows = [{"name": n, "label": label, **_state.get(n, {"state": "waiting", "ms": None})} for n, label in _order]
    done = bool(rows) and all(r["state"] in ("ready", "failed") for r in rows)
    return {"ready": done and all(r["state"] == "ready" for r in rows), "done": done, "steps": rows}
