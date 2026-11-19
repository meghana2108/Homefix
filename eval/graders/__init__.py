"""One grader per modality: grade(item, ours, ref) -> GradeResult. Graders never open files.

Shared helpers for all graders live here.
"""

from __future__ import annotations

from rapidfuzz import fuzz

from eval.types import norm

FUZZY_HIT = 80  # docs/EVAL.md: token_set_ratio >= 80 counts as a hit


def as_list(value) -> list[str]:
    """A reference may be one value or a list of accepted values (synonyms)."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value if v is not None and str(v).strip()]
    return [str(value)] if str(value).strip() else []


def fuzzy(ours: str, refs: list[str]) -> float:
    """Best token_set_ratio of norm(ours) against any accepted reference, 0-100."""
    a = norm(ours)
    return max((float(fuzz.token_set_ratio(a, norm(r))) for r in refs), default=0.0) if a else 0.0
