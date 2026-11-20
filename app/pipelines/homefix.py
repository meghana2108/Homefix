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
    final_for,
)
from app.pipelines import text
from app.prompts import READ_PROMPT, READ_PROMPT_2

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


def manuals_mentioning(code: str) -> list[dict]:
    """The manuals on the shelf whose text has this code as a word (E21 matches "E21" and "E-21")."""
    m = re.fullmatch(r"([A-Za-z]+)-?(\d+)", code)
    pat = re.compile(rf"\b{m.group(1)}-?{m.group(2)}\b", re.IGNORECASE) if m else re.compile(re.escape(code))
    out = []
    for m in list_manuals():
        try:
            _, pages = text.load_manual(m["id"])
        except (OSError, RuntimeError, ValueError):
            continue
        if any(pat.search(p) for p in pages):
            out.append(m)
    return out


def run(req: PipelineRequest, ctx: Ctx) -> Iterator[Event]:
    from app.clarify import (
        code_clarify,
        is_vague,
        manual_clarify,
        mentions_a_code,
        photo_clarify,
        two_codes_clarify,
    )
    from app.orchestrate import AUTO_MANUAL
    from app.pipelines import image

    if image.needs_danger_look(req.message):  # "What's wrong with it?": look for danger before the manual
        found: list = []
        yield from image.look_for_danger(ctx, image.images_of(req), found)
        if found:
            yield from image.stop_for_danger(ctx, req, found[0], "homefix")
            return
    typed = read_display_code(req.message)  # a code the person typed ("It shows E24") wins over the photo
    reading = ""
    code = typed
    if typed is None:
        images = image.images_of(req)
        reads: list[str] = []
        for prompt in (READ_PROMPT, READ_PROMPT_2):  # two reads, worded differently: they must agree on the code
            parts: list[str] = []
            for ev in image.read_quietly(ctx, images, parts, prompt):
                yield ev
                if isinstance(ev, Refusal):
                    yield final_for(ctx, "homefix", "manual_lookup")
                    return
            reads.append("".join(parts))
        reading = reads[0]
        codes = [read_display_code(r) for r in reads]
        if codes[0] != codes[1]:
            found = [c for c in dict.fromkeys(codes) if c]
            yield from image.ask_back(ctx, req, two_codes_clarify(req.message, reads[0], reads[1], found), "homefix")
            return
        code = codes[0]
    if code is None:
        if mentions_a_code(req.message):  # they say there's a code and we can't see one: ask for it
            yield from image.ask_back(ctx, req, code_clarify(reading), "homefix")
            return
        if is_vague(req.message):  # "What does this mean?" with no code on it: ask, don't guess
            yield from image.ask_back(ctx, req, photo_clarify(reading), "homefix")
            return
        # A specific question ("What does COOKTOP ON mean?"): answer it from the photo, without guessing.
        yield from image.answer_question(PipelineRequest(req.message, req.attachments, "qa", None), ctx, reading)
        return
    yield Status(stage="generating", detail=f"found {code}")
    manual_id = req.manual_id
    if manual_id == AUTO_MANUAL:  # the question named no appliance: the code picks the manual
        having = manuals_mentioning(code)
        if not having:
            msg = MESSAGES["code_in_no_manual"].format(code=code)
            yield Refusal(reason="not_in_document", message=msg)
            yield final_for(ctx, "homefix", "manual_lookup", model=ctx.memory.tag("brain"))
            return
        if len(having) > 1:
            yield from image.ask_back(ctx, req, manual_clarify(req.message, having, code), "homefix")
            return
        manual_id = having[0]["id"]
        yield Status(stage="routing", detail=f"Using the manual: {having[0]['title']}")
    q = PipelineRequest(f"What does error code {code} mean and what should I do?", [],
                        "doc_qa", manual_id)
    for ev in text.run(q, ctx):
        if isinstance(ev, Final):
            ev = ev.model_copy(update={"modality": "homefix", "question_type": "manual_lookup"})
        yield ev
