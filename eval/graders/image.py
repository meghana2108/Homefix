"""Image grader (docs/EVAL.md).

Count questions -> "count_exact": hit when the first number in our answer equals the reference.
Everything else -> "fuzzy": token_set_ratio of norm(ours) vs norm(reference), hit at >= 80.
"""

from __future__ import annotations

from app.numbers import first_int
from eval.graders import FUZZY_HIT, as_list, fuzzy
from eval.types import REF_KEYS, GradeResult, PackItem, RunRecord


def grade(item: PackItem, ours: RunRecord, ref: dict) -> GradeResult:
    refs = as_list(ref.get(REF_KEYS["answer"]))
    if ours.question_type == "count":
        ref_nums = {n for n in (first_int(r) for r in refs) if n is not None}
        if not ref_nums:
            return GradeResult(item.id, "count_exact", 0.0, False, "no reference answer")
        got = first_int(ours.answer or "")
        hit = got is not None and got in ref_nums
        return GradeResult(item.id, "count_exact", 1.0 if hit else 0.0, hit)
    if not refs:
        return GradeResult(item.id, "fuzzy", 0.0, False, "no reference answer")
    score = fuzzy(ours.answer or "", refs)
    return GradeResult(item.id, "fuzzy", score, score >= FUZZY_HIT)
