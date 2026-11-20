"""Shared contract: SSE events, messages, request types. frontend/src/contract.ts mirrors this."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from app.models.memory import MemoryManager
    from app.settings import Profile

Stage = Literal["converting", "safety_check", "routing", "loading_model", "transcribing",
                "labeling_sounds", "extracting_frames", "retrieving", "generating",
                "verifying", "running_code"]
RefusalReason = Literal["safety", "unsupported_file", "empty_input", "too_large",
                        "no_document", "not_in_document", "model_unavailable", "timeout"]
Modality = Literal["image", "audio", "text", "code", "video", "homefix", "none"]
QuestionType = Literal["describe", "count", "read", "qa", "motion", "speech", "sound",
                       "doc_qa", "code_gen", "manual_lookup", "none"]
ProfileName = Literal["full", "lite"]
AttachmentKind = Literal["image", "audio", "video", "document", "data"]


class Status(BaseModel):
    type: Literal["status"] = "status"
    stage: Stage                    # step now running, e.g. "loading_model"
    detail: str | None = None       # extra words for the chip, e.g. "loading qwen2.5-coder:3b"
    ms: int | None = None           # how long the step took when known, e.g. 6400


class Token(BaseModel):
    type: Literal["token"] = "token"
    text: str                       # one streamed chunk of the brain's answer


class Transcript(BaseModel):
    type: Literal["transcript"] = "transcript"
    text: str                       # full Whisper transcript
    seconds: float                  # audio length in seconds


class SoundLabel(BaseModel):
    label: str                      # one vocabulary entry
    score: float                    # CLAP probability 0-1


class SoundLabels(BaseModel):
    type: Literal["sound_labels"] = "sound_labels"
    labels: list[SoundLabel]        # exactly audio.top_k, highest score first
    is_speech: bool                 # False on the sound path


class Frames(BaseModel):
    type: Literal["frames"] = "frames"
    timestamps: list[float]         # seconds of each sampled frame


class Citation(BaseModel):
    type: Literal["citation"] = "citation"
    quote: str                      # span copied from the document, as found there
    page: int | None                # 1-based page; None for .txt/.md/.docx and inline docs
    source: str                     # file name shown to the user
    score: float                    # verifier match 0-100


class CodeResult(BaseModel):
    type: Literal["code_result"] = "code_result"
    code: str                       # the final function source shown in the panel
    passed: bool                    # True when every doctest passed and at least one ran
    tests_run: int                  # doctest examples attempted
    failures: int                   # doctest examples failed
    output_tail: str                # last 1,500 chars of the sandbox output
    attempts: int                   # 1, or 2 after one retry


class ClarifyOption(BaseModel):
    label: str                      # button text, e.g. "What does “COOKTOP ON” mean?"
    message: str                    # the question sent when it's clicked (same files go with it)
    manual_id: str | None = None    # set when the reply picks a manual


class Clarify(BaseModel):
    """HomeFix asks instead of guessing. Final.answer repeats `question`."""
    type: Literal["clarify"] = "clarify"
    question: str                   # what HomeFix needs to know, one or two sentences
    seen: str | None                # what it could read in the photo, verbatim; None if nothing
    options: list[ClarifyOption]    # one-click replies; the user can also type one


class Refusal(BaseModel):
    type: Literal["refusal"] = "refusal"
    reason: RefusalReason
    message: str                    # shown verbatim
    category: str | None = None     # safety only: gas, sparks, smoke_fire, exposed_wires, water_electric, shock


class Error(BaseModel):
    type: Literal["error"] = "error"
    stage: Stage                    # last stage started before the crash
    message: str                    # one plain sentence (MESSAGES["pipeline_crash"])
    retryable: bool                 # True: the UI shows "Try again"


class Final(BaseModel):
    type: Literal["final"] = "final"
    answer: str                     # complete answer text; "" after a refusal or error
    modality: Modality              # pipeline that ran, or "none"
    question_type: QuestionType     # from the router, or "none"
    latency_ms: int = 0             # set by handle(): POST received -> final
    profile: ProfileName
    model: str | None = None        # main model used; None if none ran


Event = Annotated[Status | Token | Transcript | SoundLabels | Frames | Citation | CodeResult | Clarify | Refusal
                  | Error | Final, Field(discriminator="type")]

EVENT_TYPES: tuple[str, ...] = tuple(
    cls.model_fields["type"].default
    for cls in (Status, Token, Transcript, SoundLabels, Frames, Citation, CodeResult, Clarify,
                Refusal, Error, Final)
)

MESSAGES: dict[str, str] = {
    "empty_input": "Type a question or attach a file.",
    "empty_doc_question": "Ask a question about the document.",
    "too_many_files": "Attach up to 4 files at a time.",
    "too_large": "That file is over 200 MB. Try a shorter clip or a smaller photo.",
    "unsupported_ext": "I can't open .{ext} files. Try a photo, audio, video, PDF, Word, text or CSV file.",
    "empty_file": "That file is empty.",
    "no_document": "Attach a file or pick a manual, and I'll answer from it. HomeFix only answers from what you give it.",
    "not_in_document": "The document doesn't contain the answer.",
    "ollama_down": "The local model server isn't running. Start Ollama and try again.",
    "model_missing": "The {role} model isn't installed. Run scripts/pull_models.sh.",
    "timeout": "The model took too long. Try a shorter clip or a smaller question.",
    "pipeline_crash": "Something went wrong in the {modality} step. Other questions still work.",
    "stub": "This pipeline isn't built yet.",
    "first_file_only": "Only the first file was used.",
    "video_trimmed": "Used the first 120 s.",
    "no_code_block": "No code block found.",
    "no_examples": "No examples to check.",
    "code_timeout": "Timed out after {s} s.",
    "function_missing": "Function {name} not found.",
    "code_in_no_manual": "None of the manuals HomeFix has mention {code}. Pick the right manual, or add it to data/manuals/.",
    "cant_tell": "I can't tell.",
}


def to_sse(event: Event) -> dict[str, str]:
    """{"event": event.type, "data": event.model_dump_json()} for sse-starlette."""
    return {"event": event.type, "data": event.model_dump_json()}


class UnsupportedFile(Exception):
    """str(e) is the user message (MESSAGES["unsupported_ext"] or ["empty_file"])."""


class ModelUnavailable(Exception):
    """str(e) is the user message (MESSAGES["ollama_down"] or ["model_missing"])."""


class ModelTimeout(Exception):
    """str(e) == MESSAGES["timeout"]."""


@dataclass
class Attachment:
    path: Path | None              # normalized file on disk; None for an inline document from eval
    kind: AttachmentKind           # what convert.py decided
    original_name: str             # name as uploaded
    pages: list[str] | None = None # documents only: text per page, page 1 first
    notes: list[str] = field(default_factory=list)  # user-facing notes


@dataclass
class PipelineRequest:
    message: str                   # user text, stripped; may be ""
    attachments: list[Attachment]  # after convert; [] when none
    question_type: QuestionType    # from the router
    manual_id: str | None = None   # stem of a PDF in data/manuals/


@dataclass
class Route:
    modality: Modality             # pipeline to run; "none" when refusal is set
    question_type: QuestionType
    refusal: Refusal | None = None # set when the router itself says no
    note: str | None = None        # e.g. MESSAGES["first_file_only"], sent as a status detail


@dataclass
class Ctx:
    profile: Profile             # parsed YAML (app/settings.py)
    memory: MemoryManager        # app/models/memory.py
    deadline_s: float = 90.0       # per model call; from profile.server.model_call_timeout_s


def final_for(ctx: Ctx, modality: Modality, question_type: QuestionType, answer: str = "",
              model: str | None = None) -> Final:
    """Builds a Final with profile=ctx.profile.name and latency_ms=0 (handle() fills it)."""
    return Final(answer=answer, modality=modality, question_type=question_type,
                 latency_ms=0, profile=ctx.profile.name, model=model)


# Every pipeline module exposes exactly this:
# def run(req: PipelineRequest, ctx: Ctx) -> Iterator[Event]