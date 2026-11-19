"""POST /api/chat: save uploads to a temp folder, stream handle() as SSE, delete the folder."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path, PurePath
from typing import Annotated

from fastapi import APIRouter, File, Form, Request, UploadFile
from sse_starlette.sse import EventSourceResponse
from starlette.concurrency import iterate_in_threadpool, run_in_threadpool

from app.contracts import to_sse
from app.orchestrate import handle

router = APIRouter()
CHUNK = 1024 * 1024


def _save(upload: UploadFile, dest: Path, limit: int) -> None:
    """Copy in 1 MB chunks and stop just past `limit`, so a huge upload never fills memory or
    disk. handle() then sees a file over the limit and answers too_large."""
    written = 0
    with dest.open("wb") as out:
        while written <= limit:
            chunk = upload.file.read(CHUNK)
            if not chunk:
                break
            out.write(chunk)
            written += len(chunk)


@router.post("/api/chat")
async def chat(
    request: Request,
    message: Annotated[str, Form()] = "",
    files: Annotated[list[UploadFile] | None, File()] = None,
    manual_id: Annotated[str | None, Form()] = None,
) -> EventSourceResponse:
    from app.api.main import get_ctx

    ctx = get_ctx(request)
    uploads = files or []
    tmp = Path(tempfile.mkdtemp(prefix="homefix_"))
    limit = ctx.profile.server.max_file_mb * 1024 * 1024
    paths: list[Path] = []
    names: list[str] = []
    for i, up in enumerate(uploads[: ctx.profile.server.max_files + 1]):  # one extra is enough to refuse
        name = PurePath((up.filename or f"file{i}").replace("\\", "/")).name or f"file{i}"
        dest = tmp / f"upload_{i}{PurePath(name).suffix.lower()}"
        await run_in_threadpool(_save, up, dest, limit)
        paths.append(dest)
        names.append(name)

    events = handle(message, paths, manual_id or None, ctx, original_names=names)

    async def stream():
        try:
            async for ev in iterate_in_threadpool(events):
                yield to_sse(ev)
        finally:
            try:
                events.close()
            except ValueError:  # still running in its thread (client left mid-answer)
                pass
            shutil.rmtree(tmp, ignore_errors=True)

    return EventSourceResponse(stream())
