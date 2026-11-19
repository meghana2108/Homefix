"""Shapes eval passes around. Nothing here reads files."""

from __future__ import annotations

import re
import string
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PackItem:
    id: str                 # pack item ID: the only pack detail that may appear in committed files
    modality: str           # "image" | "audio" | "text" | "code" | "video"
    question: str           # the prompt or question text (never written to committed files)
    path: Path | None       # media file, if any
    meta: dict = field(default_factory=dict)  # "subtype", "test_path" (code), "inline_document" (text), ...


@dataclass
class RunRecord:
    """One line of results/raw/<run_id>.jsonl."""
    run_id: str
    item_id: str
    modality: str
    question_type: str
    answer: str
    refusal_reason: str | None
    code: str | None
    sound_labels: list[str]
    latency_ms: int
    peak_mem_gb: float
    profile: str
    model: str | None
    transcript: str | None = None   # Whisper's text when a transcript event was sent (speech WER)


@dataclass
class GradeResult:
    item_id: str
    metric: str             # e.g. "count_exact", "fuzzy", "wer", "top1", "pass@1"; "todo" for a stub
    score: float
    hit: bool
    note: str = ""


# Our name -> key in a reference record. Confirm against the real pack when it arrives and change
# only here; graders read references as ref.get(REF_KEYS["answer"]).
REF_KEYS: dict[str, str] = {
    "answer": "answer",            # reference answer text / number / label / direction
    "answerable": "answerable",    # text items: False for unanswerable (SQuAD 2.0-style)
    "transcript": "transcript",    # speech items: reference transcript for WER
}

_ARTICLES = re.compile(r"\b(a|an|the)\b")
_PUNCT = str.maketrans("", "", string.punctuation)


def norm(text: str) -> str:
    """EVAL.md: lowercase, strip punctuation and articles (a, an, the), collapse whitespace."""
    text = str(text).lower().translate(_PUNCT)
    return " ".join(_ARTICLES.sub(" ", text).split())
