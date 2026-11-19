"""Video grader (docs/EVAL.md).

Reference is a number -> "count_exact" (first integer in our answer, digits or number words).
Reference is a direction -> "direction" (first direction word in our answer; synonyms such as
"anticlockwise" and "towards" accepted). Anything else -> "fuzzy", hit at token_set_ratio >= 80.
The kind comes from the reference, not from our router.
"""

from __future__ import annotations

import re

from app.numbers import NUMBER_WORDS, first_int
from eval.graders import FUZZY_HIT, as_list, fuzzy
from eval.types import REF_KEYS, GradeResult, PackItem, RunRecord

CANONICAL = {
    "left": "left", "right": "right", "up": "up", "upward": "up", "upwards": "up",
    "down": "down", "downward": "down", "downwards": "down", "toward": "toward", "towards": "toward",
    "away": "away", "clockwise": "clockwise", "counterclockwise": "counterclockwise",
    "counter-clockwise": "counterclockwise", "anticlockwise": "counterclockwise",
    "anti-clockwise": "counterclockwise",
}
# Longest first, so "counterclockwise" is never read as "clockwise".
_DIRECTION = re.compile(r"\b(" + "|".join(sorted(map(re.escape, CANONICAL), key=len, reverse=True)) + r")\b",
                        re.IGNORECASE)


def first_direction(text: str) -> str | None:
    m = _DIRECTION.search(text)
    return CANONICAL[m.group(1).lower()] if m else None


def _as_count(value) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    s = str(value).strip().lower()
    if s.isdigit():
        return int(s)
    return NUMBER_WORDS.get(s)


def grade(item: PackItem, ours: RunRecord, ref: dict) -> GradeResult:
    raw = ref.get(REF_KEYS["answer"])
    answers = as_list(raw)
    if not answers:
        return GradeResult(item.id, "fuzzy", 0.0, False, "no reference answer")

    count = _as_count(raw) if not isinstance(raw, (list, tuple)) else None
    if count is not None:
        got = first_int(ours.answer)
        return GradeResult(item.id, "count_exact", float(got == count), got == count,
                           f"ours={got} ref={count}")

    directions = {CANONICAL.get(a.strip().lower()) for a in answers} - {None}
    if directions:
        got = first_direction(ours.answer)
        hit = got in directions
        return GradeResult(item.id, "direction", float(hit), hit, f"ours={got}")

    score = fuzzy(ours.answer, answers)
    return GradeResult(item.id, "fuzzy", score, score >= FUZZY_HIT)
