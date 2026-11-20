"""What a question is after, by meaning as well as by words. Two judgments, each the word rule OR the meaning:

- problem: something is wrong ("the fridge sounds weird"), so escalating to the landlord is offered (a quiet
  link; the renter chooses). A plain question ("Is it heating or cooling?") gets nothing.
- vague:   no subject of its own ("what's this thingy?"), so on a display HomeFix asks back, and on any photo it
  looks for danger first.

The meaning side only ever adds: it can turn a question into a problem or a vague one, never the reverse, so it
can only make HomeFix ask, look or offer more, never less. Examples: config/intent_examples.yaml.
"""

from __future__ import annotations

import logging
import os
import re
from functools import lru_cache
from typing import Literal

import numpy as np
import yaml

from app import clarify
from app.settings import ROOT

log = logging.getLogger(__name__)
CONFIG = ROOT / "config/intent_examples.yaml"

# The word rule for "problem" (the same list the UI used before this file existed).
PROBLEM_WORDS = re.compile(
    r"\b(broken|break(s|ing)?|not working|(does|is|are|do|did|was)n'?t (work|drain|turn|start|heat|cool|close|open|"
    r"flush|stop)|won'?t|stopped|leak\w*|drip\w*|flood\w*|overflow\w*|mou?ld\w*|damp|smell\w*|odou?r|noise|noisy|"
    r"loud|beep\w*|chirp\w*|alarm\w*|error|code|fault\w*|flash\w*|blink\w*|problem|issue|wrong|fix|repair\w*|"
    r"damage\w*|crack\w*|clog\w*|block\w*|jam\w*|trip\w*|spark\w*|burn\w*|stuck|no (heat|hot water|power|water)|"
    r"too (hot|cold)|freez\w*|ice|pest\w*|roach\w*|mice|mouse|rats?|bugs?)\b", re.IGNORECASE)


@lru_cache(maxsize=1)
def _config() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _examples() -> dict[str, np.ndarray]:
    from app.safety_semantic import _embed

    cfg = _config()
    return {side: _embed(list(cfg[side])) for side in ("problem", "question", "vague", "specific")}


def lean(text: str, side: str, other: str) -> float:
    """How much closer the text is to `side`'s examples than to `other`'s (positive = closer to `side`)."""
    from app.safety_semantic import vector

    ex = _examples()
    v = vector(text)
    return float(np.max(ex[side] @ v) - np.max(ex[other] @ v))


def _by_meaning(text: str, side: str, other: str, margin_key: str, margin: float | None) -> bool:
    if not text.strip() or os.environ.get("HOMEFIX_SAFETY_MEANING") == "off":
        return False
    m = _config()[margin_key] if margin is None else margin
    try:
        return lean(text, side, other) >= m
    except Exception as e:  # noqa: BLE001 - the word rule still decides
        log.warning("meaning-based intent unavailable: %s", e)
        return False


def is_problem(text: str, margin: float | None = None) -> bool:
    return bool(PROBLEM_WORDS.search(text)) or _by_meaning(text, "problem", "question", "problem_margin", margin)


def is_vague(text: str, margin: float | None = None) -> bool:
    if clarify.is_vague(text):
        return True
    return _by_meaning(text, "vague", "specific", "vague_margin", margin)


def intent_of(text: str) -> Literal["problem", "question"]:
    return "problem" if is_problem(text) else "question"
