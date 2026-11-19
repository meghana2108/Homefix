"""Numbers in text: the first integer (digits or word) and a normalized set of all numbers."""

from __future__ import annotations

import re

NUMBER_WORDS = {w: i for i, w in enumerate([
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven",
    "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty"])}
_INT = re.compile(r"\b(\d+|" + "|".join(NUMBER_WORDS) + r")\b", re.IGNORECASE)
_ANY = re.compile(r"\b(\d+(?:\.\d+)?|" + "|".join(NUMBER_WORDS) + r")\b", re.IGNORECASE)


def first_int(text: str) -> int | None:
    m = _INT.search(text)
    if not m:
        return None
    tok = m.group(1).lower()
    return int(tok) if tok.isdigit() else NUMBER_WORDS[tok]


def numbers_in(text: str) -> set[str]:
    """Normalized numbers: "30", "2.5"; number words become digits ("four" -> "4")."""
    out: set[str] = set()
    for m in _ANY.finditer(text):
        tok = m.group(1).lower()
        out.add(str(NUMBER_WORDS[tok]) if tok in NUMBER_WORDS else tok)
    return out
