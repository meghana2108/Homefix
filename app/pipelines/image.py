"""Image pipeline: describe, count (number first), read text, or answer a question.

All attached images (up to 4) go to the brain in one call. Tokens stream live.
"""

from __future__ import annotations

from collections.abc import Iterator

from app.contracts import Ctx, Event, PipelineRequest, Refusal, final_for
from app.pipelines.common import collect, stream_brain
from app.prompts import DESCRIBE_PROMPT, READ_PROMPT, count_prompt, force_number_first, qa_prompt

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


def run(req: PipelineRequest, ctx: Ctx) -> Iterator[Event]:
    images = [a.path for a in req.attachments if a.kind == "image" and a.path][:MAX_IMAGES]
    messages = [{"role": "user", "content": _prompt(req)}]
    parts: list[str] = []
    was_refused = False
    for ev in collect(stream_brain(ctx, messages, images), parts):
        was_refused = was_refused or isinstance(ev, Refusal)
        yield ev
    answer = "".join(parts).strip()
    if was_refused:
        answer = ""
    elif req.question_type == "count":
        answer = force_number_first(answer)
    yield final_for(ctx, "image", req.question_type, answer, model=ctx.memory.tag("brain"))
