"""Image pipeline: describe, count (number first), read text, or answer a question.

All attached images (up to 4) go to the brain in one call. Tokens stream live.
A vague question ("What is this?", or none) gets the display read and a question back instead of a guess, and
a question the photo can't answer gets a question back too (app/clarify.py).
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

from app.clarify import (
    cant_tell_clarify,
    clean_reading,
    is_vague,
    looks_like_display,
    photo_clarify,
)
from app.contracts import (
    MESSAGES,
    Clarify,
    Ctx,
    Event,
    PipelineRequest,
    Refusal,
    Status,
    Token,
    final_for,
)
from app.pipelines.common import collect, stream_brain
from app.prompts import (
    DESCRIBE_PROMPT,
    READ_PROMPT,
    count_prompt,
    display_prompt,
    force_number_first,
    qa_prompt,
)
from app.safety import SafetyHit, check_observation, refusal_for

MAX_IMAGES = 4


def _prompt(req: PipelineRequest) -> str:
    q = req.question_type
    if q == "count":
        return count_prompt(req.message)
    if q == "read":
        return READ_PROMPT
    if q == "describe" or not req.message:
        return DESCRIBE_PROMPT
    return qa_prompt(req.message)


def images_of(req: PipelineRequest) -> list[Path]:
    return [a.path for a in req.attachments if a.kind == "image" and a.path][:MAX_IMAGES]


def read_quietly(ctx: Ctx, images: list[Path], sink: list[str]) -> Iterator[Event]:
    """Read the display without streaming it as the answer. Passes status and refusal events through."""
    for ev in collect(stream_brain(ctx, [{"role": "user", "content": READ_PROMPT}], images), sink):
        if not isinstance(ev, Token):
            yield ev


def clarify_text(c: Clarify) -> str:
    """Final.answer for a question back: the question, then what was read (the CLI and eval see this)."""
    if not c.seen:
        return c.question
    seen = ", ".join(ln.strip() for ln in c.seen.splitlines() if ln.strip())
    return f"{c.question} What I could read: {seen}."


# A focused look for danger, asked before a vague or safety question about a photo. Measured on the M2 with 4 real
# hazard photos and 6 safe ones: two looks named the danger in 4/4 and said "None" on 6/6 safe photos (a single
# cold look missed 3 of 4), so it looks twice and either look naming a sign stops.
DANGER_LOOK = ("Look only for these signs of danger: burn or scorch marks, melted plastic, smoke, sparks, exposed or "
               "frayed wires, water on or near electrical parts. If you see any, name them in one short sentence. "
               "If you see none of them, reply exactly: None.")
DANGER_LOOKS = 2
_SAFETY_Q = re.compile(r"\b(safe|unsafe|okay|ok|alright|normal|dangerous|danger|hazard\w*|wrong|fine|damaged|"
                       r"broken|use|touch)\b", re.IGNORECASE)
_NONE = re.compile(r"^\W*none\b|\bno (signs?|danger)\b|\bnone of (them|these|those)\b|\bi (can )?see no(ne|thing)?\b|"
                   r"^\W*nothing\b", re.IGNORECASE)


def needs_danger_look(message: str) -> bool:
    """Vague ("What is this?") or about safety ("Is this okay to use?"): look for danger before answering."""
    return is_vague(message) or bool(_SAFETY_Q.search(message))


def danger_named(text: str) -> SafetyHit | None:
    """What a danger look found: None for "None"/"no signs"; anything else is a sign (unsure means stop)."""
    t = text.strip()
    if not t or _NONE.search(t):
        return None
    return check_observation(t) or SafetyHit("smoke_fire", f"named: {t[:60]}")


def look_for_danger(ctx: Ctx, images: list[Path], found: list[SafetyHit]) -> Iterator[Event]:
    """Up to DANGER_LOOKS focused looks; the first one that names a sign goes into `found`."""
    yield Status(stage="safety_check", detail="Looking for signs of danger in the photo")
    for _ in range(DANGER_LOOKS):
        parts: list[str] = []
        for ev in collect(stream_brain(ctx, [{"role": "user", "content": DANGER_LOOK}], images), parts):
            if isinstance(ev, Refusal):
                return  # the model isn't answering: the normal path reports it
            if not isinstance(ev, Token):
                yield ev
        hit = danger_named("".join(parts))
        if hit:
            found.append(hit)
            return


def stop_for_danger(ctx: Ctx, req: PipelineRequest, hit: SafetyHit, modality: str = "image") -> Iterator[Event]:
    seen = hit.pattern[len("named: "):] if hit.pattern.startswith("named: ") else hit.category.replace("_", " ")
    yield Status(stage="safety_check", detail=f"Seen in the photo: {seen}")
    yield refusal_for(hit)
    yield final_for(ctx, modality, req.question_type, model=ctx.memory.tag("brain"))


def ask_back(ctx: Ctx, req: PipelineRequest, c: Clarify, modality: str = "image") -> Iterator[Event]:
    yield c
    yield final_for(ctx, modality, req.question_type, clarify_text(c), model=ctx.memory.tag("brain"))


def _cant_tell(answer: str) -> bool:
    return MESSAGES["cant_tell"].lower().rstrip(".") in answer.lower()


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _only_echoes(answer: str, reading: str) -> bool:
    """The model gave back the display instead of answering: three or more words, all of them read off it."""
    words = _words(answer)
    return len(words) >= 3 and set(words) <= set(_words(reading))


def answer_question(req: PipelineRequest, ctx: Ctx, reading: str | None = None) -> Iterator[Event]:
    """A specific question about a photo. A display (words with numbers) is answered from its words alone;
    anything else from the photo. "I can't tell" anywhere in the answer becomes a question back."""
    images = images_of(req)
    if reading is None:
        parts: list[str] = []
        for ev in read_quietly(ctx, images, parts):
            yield ev
            if isinstance(ev, Refusal):
                yield final_for(ctx, "image", "qa")
                return
        reading = "".join(parts)
    display = looks_like_display(reading)
    prompt = display_prompt(reading, req.message) if display else qa_prompt(req.message)
    parts = []
    for ev in collect(stream_brain(ctx, [{"role": "user", "content": prompt}], None if display else images), parts):
        yield ev
        if isinstance(ev, Refusal):
            yield final_for(ctx, "image", "qa")
            return
    answer = "".join(parts).strip()
    seen = check_observation(answer)
    if seen:
        yield from stop_for_danger(ctx, req, seen)
        return
    if _cant_tell(answer) or (display and _only_echoes(answer, reading)):
        yield from ask_back(ctx, req, cant_tell_clarify(reading if display else None))
        return
    yield final_for(ctx, "image", "qa", answer, model=ctx.memory.tag("brain"))


def run(req: PipelineRequest, ctx: Ctx) -> Iterator[Event]:
    images = images_of(req)
    if req.question_type in ("describe", "qa", "read") and needs_danger_look(req.message):
        found: list[SafetyHit] = []
        yield from look_for_danger(ctx, images, found)
        if found:
            yield from stop_for_danger(ctx, req, found[0])
            return
    reading: str | None = None
    if req.question_type in ("describe", "qa") and is_vague(req.message):
        # A display (words with numbers) is where a guess goes wrong ("a timer" for a clock): ask. A scene
        # ("What's in this photo?") just wants describing.
        parts: list[str] = []
        for ev in read_quietly(ctx, images, parts):
            yield ev
            if isinstance(ev, Refusal):
                yield final_for(ctx, "image", req.question_type)
                return
        reading = "".join(parts)
        if looks_like_display(reading):
            yield from ask_back(ctx, req, photo_clarify(reading))
            return
    if req.question_type == "qa":
        yield from answer_question(req, ctx, reading)
        return

    messages = [{"role": "user", "content": _prompt(req)}]
    parts = []
    was_refused = False
    for ev in collect(stream_brain(ctx, messages, images), parts):
        was_refused = was_refused or isinstance(ev, Refusal)
        yield ev
    answer = "".join(parts).strip()
    if was_refused:
        answer = ""
    elif req.question_type == "count":
        answer = force_number_first(answer)
    elif req.question_type == "read" and clean_reading(answer):
        answer = clean_reading(answer)  # "<the text> I can't tell." -> "<the text>"
    seen = check_observation(answer) if req.question_type != "count" else None
    if seen:  # the description itself says it sees danger
        yield from stop_for_danger(ctx, req, seen)
        return
    yield final_for(ctx, "image", req.question_type, answer, model=ctx.memory.tag("brain"))
