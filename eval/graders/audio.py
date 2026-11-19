"""Audio grader (docs/EVAL.md).

Speech: with a reference answer -> "fuzzy" on our answer (WER in the note when a reference
transcript exists); with only a reference transcript -> "wer", hit when <= 0.15.
Sounds: "top1" (hit when our first label matches), note "top3_hit=true|false". A label matches
when token_set_ratio(norm(label), norm(ref)) >= 80.
Speech vs sound comes from the pack item (its subtype or reference), not from our router.
"""

from __future__ import annotations

import jiwer

from eval.graders import FUZZY_HIT, as_list, fuzzy
from eval.types import REF_KEYS, GradeResult, PackItem, RunRecord, norm

WER_HIT = 0.15


def _is_sound(item: PackItem, ours: RunRecord, ref: dict) -> bool:
    sub = str(item.meta.get("subtype", "")).lower()
    if "sound" in sub or sub in ("esc", "environmental", "audio_event"):
        return True
    if "speech" in sub or "asr" in sub or REF_KEYS["transcript"] in ref:
        return False
    return ours.question_type == "sound"


def _wer(reference: str, hypothesis: str) -> float:
    r, h = norm(reference), norm(hypothesis)
    if not r:
        return 0.0 if not h else 1.0
    return float(jiwer.wer(r, h))


def _sound(item: PackItem, ours: RunRecord, refs: list[str]) -> GradeResult:
    labels = ours.sound_labels[:3]
    hits = [fuzzy(label, refs) >= FUZZY_HIT for label in labels]
    top1 = bool(hits and hits[0])
    score = fuzzy(labels[0], refs) if labels else 0.0
    return GradeResult(item.id, "top1", score, top1, f"top3_hit={'true' if any(hits) else 'false'}")


def grade(item: PackItem, ours: RunRecord, ref: dict) -> GradeResult:
    answers = as_list(ref.get(REF_KEYS["answer"]))
    ref_transcript = ref.get(REF_KEYS["transcript"])

    if _is_sound(item, ours, ref):
        if not answers:
            return GradeResult(item.id, "top1", 0.0, False, "no reference answer")
        return _sound(item, ours, answers)

    our_text = ours.transcript if ours.transcript is not None else ours.answer
    if answers:
        score = fuzzy(ours.answer, answers)
        note = f"wer={_wer(ref_transcript, our_text):.2f}" if isinstance(ref_transcript, str) else ""
        return GradeResult(item.id, "fuzzy", score, score >= FUZZY_HIT, note)
    if isinstance(ref_transcript, str):
        w = _wer(ref_transcript, our_text)
        return GradeResult(item.id, "wer", w, w <= WER_HIT)
    return GradeResult(item.id, "wer", 1.0, False, "no reference answer")
