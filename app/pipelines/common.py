"""Helpers every brain-using pipeline shares (image, video, audio Q&A)."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path

from app.contracts import (
    MESSAGES,
    Ctx,
    Event,
    ModelTimeout,
    ModelUnavailable,
    Refusal,
    Status,
    Token,
)
from app.models import ollama_client


def stream_brain(ctx: Ctx, messages: list[dict], images: list[Path] | None = None) -> Iterator[Event]:
    """Load the brain if needed, then stream its answer as Token events.

    Ollama down / model missing -> one Refusal(model_unavailable); too slow -> Refusal(timeout).
    Either way the stream just stops; this never raises for those.
    """
    try:
        yield from ctx.memory.ensure("brain")
        tag = ctx.memory.tag("brain")
        yield Status(stage="generating", detail=tag)
        for text in ollama_client.chat_stream(
            tag, messages, images,
            num_ctx=ctx.memory.num_ctx("brain"),
            keep_alive=ctx.memory.keep_alive("brain"),
            timeout_s=ctx.deadline_s,
        ):
            yield Token(text=text)
    except ModelUnavailable as e:
        yield Refusal(reason="model_unavailable", message=str(e))
    except ModelTimeout:
        yield Refusal(reason="timeout", message=MESSAGES["timeout"])


def collect(events: Iterable[Event], sink: list[str]) -> Iterator[Event]:
    """Pass events through unchanged; append each Token's text to sink."""
    for ev in events:
        if isinstance(ev, Token):
            sink.append(ev.text)
        yield ev


def refused(events_seen: list[Event]) -> bool:
    return any(isinstance(e, Refusal) for e in events_seen)
