"""Text grader (docs/EVAL.md).

Answerable -> "answer_match": hit when a reference is inside our answer, or fuzzy >= 80.
Unanswerable (answerable is False) -> "refusal": hit only when we refused with "not_in_document".
A refusal on an answerable item is a miss.
"""

from __future__ import annotations

from eval.graders import FUZZY_HIT, as_list, fuzzy
from eval.types import REF_KEYS, GradeResult, PackItem, RunRecord, norm


def grade(item: PackItem, ours: RunRecord, ref: dict) -> GradeResult:
    if ref.get(REF_KEYS["answerable"]) is False:
        hit = ours.refusal_reason == "not_in_document"
        return GradeResult(item.id, "refusal", 1.0 if hit else 0.0, hit)

    refs = as_list(ref.get(REF_KEYS["answer"]))
    if not refs:
        return GradeResult(item.id, "answer_match", 0.0, False, "no reference answer")
    if ours.refusal_reason:
        return GradeResult(item.id, "answer_match", 0.0, False, f"refused: {ours.refusal_reason}")
    ours_n = norm(ours.answer or "")
    contained = any(norm(r) and norm(r) in ours_n for r in refs)
    score = 100.0 if contained else fuzzy(ours.answer or "", refs)
    return GradeResult(item.id, "answer_match", score, contained or score >= FUZZY_HIT)
