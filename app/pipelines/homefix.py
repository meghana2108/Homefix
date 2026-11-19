"""HomeFix pipeline: a photo of an appliance display plus a chosen manual.

Read the error code off the photo, then ask the text pipeline what the manual says about it.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

from app.contracts import (
    MESSAGES,
    Ctx,
    Event,
    Final,
    PipelineRequest,
    Refusal,
    Status,
    Token,
    final_for,
)
from app.pipelines import text
from app.pipelines.common import collect, stream_brain
from app.prompts import READ_PROMPT

MAX_IMAGES = 4
_CODE = re.compile(r"\b[A-Z]{1,3}-?\d{1,3}\b")


def read_display_code(answer: str) -> str | None:
    """First error-code-looking token in the brain's reading, or None."""
    m = _CODE.search(answer.upper())
    return m.group(0) if m else None


_JUNK_TITLES = {"title", "untitled", "document", "manual", "user manual", "pdf"}


def pretty_stem(stem: str) -> str:
    """washer_aeg_l6fbj741n -> "Washer AEG L6FBJ741N" (docs/ASSETS.md naming: <appliance>_<brand>_<model>)."""
    parts = [p for p in re.split(r"[_\-\s]+", stem) if p]
    return " ".join([parts[0].capitalize(), *(p.upper() for p in parts[1:])]) if parts else stem


def manual_title(pdf_title: str | None, stem: str) -> str:
    """The PDF's own title, unless it is empty or junk ("Title", "Microsoft Word - x.docx")."""
    t = (pdf_title or "").strip()
    if len(t) < 3 or t.lower() in _JUNK_TITLES or t.lower().startswith("microsoft word") or t.lower().endswith(".pdf"):
        return pretty_stem(stem)
    return t


def list_manuals() -> list[dict]:
    """[{id, title, pages}] for each PDF in the manuals folder that can be loaded by id."""
    folder = Path(text.MANUALS_DIR)
    if not folder.is_dir():
        return []
    out = []
    for p in sorted(folder.glob("*.pdf")):
        if text._manual_path(p.stem) is None:
            continue
        try:
            import pymupdf

            with pymupdf.open(p) as d:
                title = manual_title((d.metadata or {}).get("title"), p.stem)
                pages = d.page_count
        except (OSError, RuntimeError, ValueError):  # unreadable PDF: don't offer it
            title, pages = None, 0
        if not pages:
            continue
        out.append({"id": p.stem, "title": title, "pages": pages})
    return out


def run(req: PipelineRequest, ctx: Ctx) -> Iterator[Event]:
    images = [a.path for a in req.attachments if a.kind == "image" and a.path][:MAX_IMAGES]
    parts: list[str] = []
    for ev in collect(stream_brain(ctx, [{"role": "user", "content": READ_PROMPT}], images), parts):
        if not isinstance(ev, Token):
            yield ev
        if isinstance(ev, Refusal):
            yield final_for(ctx, "homefix", "manual_lookup")
            return
    code = read_display_code("".join(parts))
    if code is None:
        yield final_for(ctx, "homefix", "manual_lookup", MESSAGES["no_display_code"],
                        model=ctx.memory.tag("brain"))
        return
    yield Status(stage="generating", detail=f"found {code}")
    q = PipelineRequest(f"What does error code {code} mean and what should I do?", [],
                        "doc_qa", req.manual_id)
    for ev in text.run(q, ctx):
        if isinstance(ev, Final):
            ev = ev.model_copy(update={"modality": "homefix", "question_type": "manual_lookup"})
        yield ev
