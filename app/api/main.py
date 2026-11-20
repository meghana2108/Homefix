"""FastAPI app: /api/chat (SSE), /api/health, /api/manuals, /api/mic.

    uv run uvicorn app.api.main:app --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app import safety_semantic
from app.api import chat, manuals, mic
from app.contracts import Ctx
from app.models import ollama_client
from app.orchestrate import build_ctx


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not hasattr(app.state, "ctx"):
        app.state.ctx = build_ctx()
    # load the meaning-based danger net in the background, so the first question doesn't wait for it
    threading.Thread(target=safety_semantic.warm, name="warm-safety", daemon=True).start()
    yield


app = FastAPI(title="HomeFix", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(chat.router)
app.include_router(manuals.router)
app.include_router(mic.router)


def get_ctx(request: Request) -> Ctx:
    """The app's Ctx (built at startup; built here on first use when there was no startup)."""
    if not hasattr(request.app.state, "ctx"):
        request.app.state.ctx = build_ctx()
    return request.app.state.ctx


@app.get("/api/health")
def health(request: Request) -> dict:
    """Sync on purpose: FastAPI runs it in a thread, so a slow Ollama never blocks streams."""
    ctx = get_ctx(request)
    up = ollama_client.is_up()
    loaded: list[str] = []
    if up:
        try:
            loaded = ctx.memory.backend.loaded()
        except Exception:  # noqa: BLE001 - health must always answer
            loaded = []
    return {"profile": ctx.profile.name, "ollama": up,
            "models": {"brain": ctx.profile.models.brain, "coder": ctx.profile.models.coder},
            "loaded": loaded}
