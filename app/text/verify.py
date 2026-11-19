"""The quote check: no verified word-for-word quote, no answer."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from rapidfuzz import fuzz

from app.numbers import numbers_in

_TABLE = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-"})


@dataclass
class Verdict:
    ok: bool
    page: int | None
    score: float
    reason: Literal["ok", "quote_not_found", "number_not_in_quote", "quote_too_short", "no_answer",
                    "code_not_in_quote"]


def codes_in(text: str) -> set[str]:
    """Alphanumeric codes such as e21 or 9v (letters and digits in one word)."""
    return set(re.findall(r"\b(?=\w*\d)(?=\w*[a-z])\w+\b", text.lower()))


def glue_units(text: str) -> str:
    """"230 V" -> "230v" so spaced and glued units compare equal."""
    return re.sub(r"(?<=\d)\s+(?=[a-z]{1,3}\b)", "", text.lower())


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().translate(_TABLE)).strip()


def estimate_tokens(text: str) -> int:
    return int(len(text.split()) * 1.3)


def verify(answer: str | None, quote: str | None, pages: list[str], cited_page: int | None,
           threshold: float) -> Verdict:
    if answer is None:
        return Verdict(False, None, 0.0, "no_answer")
    q = normalize(quote or "")
    if len(q.split()) < 3:
        return Verdict(False, None, 0.0, "quote_too_short")
    norm = [normalize(p) for p in pages]
    page, score = None, 0.0
    for i, p in enumerate(norm):
        if q in p:
            page, score = i + 1, 100.0
            break
    if page is None:
        order = list(range(len(norm)))
        if cited_page is not None and 1 <= cited_page <= len(norm):
            order.remove(cited_page - 1)
            order.insert(0, cited_page - 1)
        best_i = None
        for i in order:
            s = fuzz.partial_ratio(q, norm[i])
            if s > score:
                best_i, score = i, s
            # prefer the cited page when it already clears the threshold
            if i == order[0] and s >= threshold:
                break
        if best_i is None or score < threshold:
            return Verdict(False, None, float(score), "quote_not_found")
        page = best_i + 1
    a, qq = glue_units(answer), glue_units(quote or "")
    if not numbers_in(a) <= numbers_in(qq):
        return Verdict(False, page, score, "number_not_in_quote")
    if not codes_in(a) <= codes_in(qq):
        return Verdict(False, page, score, "code_not_in_quote")
    return Verdict(True, page, score, "ok")
