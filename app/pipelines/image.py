"""Stub pipeline for the image modality. Replaced by its owner."""

from __future__ import annotations

from collections.abc import Iterator

from app.contracts import MESSAGES, Ctx, Event, PipelineRequest, Refusal, Status, final_for

IS_STUB = True


def run(req: PipelineRequest, ctx: Ctx) -> Iterator[Event]:
    yield Status(stage="generating")
    yield Refusal(reason="model_unavailable", message=MESSAGES["stub"])
    yield final_for(ctx, "image", req.question_type)
