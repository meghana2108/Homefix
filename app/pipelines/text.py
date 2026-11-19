"""Text pipeline: answer from a document or manual with a verified quote and page.

No verified word-for-word quote, no answer. Tokens are never streamed: the answer is shown
only after the quote has been checked against the document.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

from app.contracts import (
    MESSAGES,
    Citation,
    Ctx,
    Event,
    ModelTimeout,
    ModelUnavailable,
    PipelineRequest,
    Refusal,
    Status,
    UnsupportedFile,
    final_for,
)
from app.media.convert import read_document
from app.models import ollama_client
from app.settings import MANUALS_DIR
from app.text.retrieve import chunk_pages, top_chunks
from app.text.verify import Verdict, estimate_tokens, verify

RETRY_PROMPT = ("Your quote was not found word for word. Copy a shorter exact sentence from the "
                "text, or answer null.")

_SYSTEM = (
    "You answer questions using only the document text below. Reply with JSON only: "
    '{"answer": "<short answer>", "quote": "<words copied exactly from the document>", '
    '"page": <page number>}. The quote must be copied word for word. If the document does not '
    'contain the answer, reply {"answer": null, "quote": null, "page": null}.'
)


@lru_cache(maxsize=8)
def _read_manual(path: Path, mtime_ns: int) -> tuple[str, list[str]]:
    return path.name, read_document(path)


def _manual_path(manual_id: str) -> Path | None:
    """data/manuals/<manual_id>.pdf, or None when the id could point anywhere else."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", manual_id) or ".." in manual_id:
        return None
    p = (MANUALS_DIR / f"{manual_id}.pdf").resolve()
    return p if p.is_relative_to(MANUALS_DIR.resolve()) else None


def load_manual(manual_id: str) -> tuple[str, list[str]]:
    """(file name, pages) of data/manuals/<manual_id>.pdf. Re-read when the file changes."""
    path = _manual_path(manual_id)
    if path is None:
        raise FileNotFoundError(manual_id)
    return _read_manual(path, path.stat().st_mtime_ns)


def _parse(raw: str) -> dict | None:
    for cand in (raw, *(m.group(0) for m in [re.search(r"\{.*\}", raw, re.DOTALL)] if m)):
        try:
            obj = json.loads(cand)
        except ValueError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def _str_or_none(v: object) -> str | None:
    return v.strip() or None if isinstance(v, str) else None


def _refuse(ctx: Ctx, req: PipelineRequest, reason: str, message: str) -> Iterator[Event]:
    yield Refusal(reason=reason, message=message)  # type: ignore[arg-type]
    yield final_for(ctx, "text", req.question_type)


def _document(req: PipelineRequest) -> tuple[str, list[str], bool] | None:
    """(source name, pages, is_pdf) or None when there is nothing to answer from."""
    for a in req.attachments:
        if a.kind == "document" and a.pages is not None:
            return a.original_name, a.pages, a.original_name.lower().endswith(".pdf")
    if req.manual_id:
        try:
            name, pages = load_manual(req.manual_id)
        except (OSError, ValueError, UnsupportedFile):  # missing or unreadable file
            return None
        return name, pages, True
    return None


def run(req: PipelineRequest, ctx: Ctx) -> Iterator[Event]:
    doc = _document(req)
    if doc is None or not any(p.strip() for p in doc[1]):
        yield from _refuse(ctx, req, "no_document", MESSAGES["no_document"])
        return
    source, pages, is_pdf = doc
    cfg = ctx.profile.text
    full = "\n\n".join(f"[page {i}]\n{p}" for i, p in enumerate(pages, start=1))
    if estimate_tokens(" ".join(pages)) > cfg.full_doc_max_tokens:
        yield Status(stage="retrieving")
        chosen = top_chunks(req.message, chunk_pages(pages), cfg.rag_top_k)
        full = "\n\n".join(f"[page {c.page}]\n{c.text}" for c in chosen)
    messages = [{"role": "system", "content": _SYSTEM},
                {"role": "user", "content": f"Document:\n{full}\n\nQuestion: {req.message}"}]

    yield Status(stage="generating")
    verdict: Verdict | None = None
    answer = quote = None
    try:
        yield from ctx.memory.ensure("brain")
        for attempt in range(2):
            raw = ollama_client.chat(ctx.memory.tag("brain"), messages,
                                     num_ctx=ctx.memory.num_ctx("brain"),
                                     keep_alive=ctx.memory.keep_alive("brain"),
                                     timeout_s=ctx.deadline_s, json_format=True)
            obj = _parse(raw)
            if obj is not None:
                answer, quote = _str_or_none(obj.get("answer")), _str_or_none(obj.get("quote"))
                cited = obj.get("page")
                cited = cited if isinstance(cited, int) and not isinstance(cited, bool) else None
                if answer is None:
                    verdict = Verdict(False, None, 0.0, "no_answer")
                    break
                yield Status(stage="verifying")
                verdict = verify(answer, quote, pages, cited, cfg.quote_fuzz_threshold)
                if verdict.ok:
                    break
            if attempt == 0:
                messages = [*messages, {"role": "assistant", "content": raw},
                            {"role": "user", "content": RETRY_PROMPT}]
    except ModelUnavailable as e:
        yield from _refuse(ctx, req, "model_unavailable", str(e))
        return
    except ModelTimeout:
        yield from _refuse(ctx, req, "timeout", MESSAGES["timeout"])
        return

    if verdict is None or not verdict.ok or answer is None or quote is None:
        yield from _refuse(ctx, req, "not_in_document", MESSAGES["not_in_document"])
        return
    page = None if (len(pages) == 1 and not is_pdf) else verdict.page
    yield Citation(quote=quote, page=page, source=source, score=verdict.score)
    yield final_for(ctx, "text", req.question_type, answer, model=ctx.memory.tag("brain"))
