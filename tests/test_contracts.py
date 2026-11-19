import importlib

import pytest
from pydantic import TypeAdapter

from app.contracts import (
    EVENT_TYPES,
    MESSAGES,
    Citation,
    CodeResult,
    Error,
    Event,
    Final,
    Frames,
    PipelineRequest,
    Refusal,
    SoundLabel,
    SoundLabels,
    Status,
    Token,
    Transcript,
    to_sse,
)


def test_event_types_tuple():
    assert EVENT_TYPES == ("status", "token", "transcript", "sound_labels", "frames", "citation",
                           "code_result", "refusal", "error", "final")


def test_event_round_trip():
    events = [
        Status(stage="routing", detail="x", ms=3),
        Token(text="hi"),
        Transcript(text="E21", seconds=1.5),
        SoundLabels(labels=[SoundLabel(label="a", score=0.7)], is_speech=False),
        Frames(timestamps=[0.0, 1.9]),
        Citation(quote="q", page=None, source="m.pdf", score=100.0),
        CodeResult(code="def f(): pass", passed=True, tests_run=1, failures=0, output_tail="", attempts=1),
        Refusal(reason="safety", message="m", category="gas"),
        Error(stage="generating", message="m", retryable=True),
        Final(answer="a", modality="image", question_type="count", latency_ms=5, profile="full", model="m"),
    ]
    assert [e.type for e in events] == list(EVENT_TYPES)
    adapter = TypeAdapter(Event)
    for e in events:
        assert adapter.validate_json(e.model_dump_json()) == e


def test_to_sse():
    assert to_sse(Status(stage="routing")) == {
        "event": "status",
        "data": '{"type":"status","stage":"routing","detail":null,"ms":null}',
    }


def test_messages_complete():
    assert set(MESSAGES) == {
        "empty_input", "empty_doc_question", "too_many_files", "too_large", "unsupported_ext",
        "empty_file", "no_document", "not_in_document", "ollama_down", "model_missing", "timeout",
        "pipeline_crash", "stub", "first_file_only", "video_trimmed", "no_code_block", "no_examples",
        "code_timeout", "function_missing", "no_display_code", "cant_tell",
    }
    assert len(MESSAGES) == 21
    assert MESSAGES["not_in_document"] == "The document doesn't contain the answer."


@pytest.mark.parametrize("modality", ["image", "audio", "text", "code", "video", "homefix"])
def test_stub_pipelines_end_with_final(modality, ctx_full):
    mod = importlib.import_module(f"app.pipelines.{modality}")
    if not getattr(mod, "IS_STUB", False):
        pytest.skip("pipeline replaced")
    events = list(mod.run(PipelineRequest("", [], "none"), ctx_full))
    assert [type(e) for e in events] == [Status, Refusal, Final]
    assert events[1].reason == "model_unavailable"
    assert events[1].message == MESSAGES["stub"]
    assert events[-1].modality == modality
