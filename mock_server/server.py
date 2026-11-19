"""Mock HomeFix backend: same four paths as the real API, canned events from scripts.py.

    uv run uvicorn mock_server.server:app --port 8001
    # UI: VITE_API_URL=http://127.0.0.1:8001 npm run dev
"""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import FastAPI, File, Form, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from app.contracts import to_sse
from mock_server.scripts import BRAIN, CODER, script_for

DELAY_SCALE = 1.0  # tests set this to 0

app = FastAPI(title="HomeFix mock server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/chat")
async def chat(
    message: Annotated[str, Form()] = "",
    files: Annotated[list[UploadFile] | None, File()] = None,
    manual_id: Annotated[str | None, Form()] = None,
) -> EventSourceResponse:
    names = [f.filename or "file" for f in files or []]
    steps = script_for(message.strip(), names, manual_id or None)

    async def stream():
        for delay, event in steps:
            await asyncio.sleep(delay * DELAY_SCALE)
            yield to_sse(event)

    return EventSourceResponse(stream())


@app.get("/api/health")
async def health() -> dict:
    return {"profile": "full", "ollama": True,
            "models": {"brain": BRAIN, "coder": CODER}, "loaded": [BRAIN]}


@app.get("/api/manuals")
async def manuals() -> list[dict]:
    return [{"id": "washer_manual", "title": "washer_manual.pdf", "pages": 64}]


@app.websocket("/api/mic")
async def mic(ws: WebSocket) -> None:
    await ws.accept()
    try:
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                return
            if msg.get("bytes") is not None:
                await ws.send_json({"type": "partial", "text": "testing"})
            elif msg.get("text") and '"stop"' in msg["text"]:
                await ws.send_json({"type": "final", "text": "testing one two"})
                await ws.close()
                return
    except WebSocketDisconnect:
        return
