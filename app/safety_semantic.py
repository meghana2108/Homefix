"""Meaning-based danger net: a second safety check, after the regex in app/safety.py.

The regex catches the words we thought of ("I smell gas"). This catches paraphrases ("there's a weird sulfur
smell by the oven") by comparing the text, with the embedding model already loaded for manual search, to
hazard and safe examples in config/safety_semantic.yaml. A text closer to a hazard example than to every safe
example, by at least `margin`, stops like a regex hit.

It only ever ADDS a stop: callers run it when the regex found nothing, and nothing here can clear a regex stop.
If the embedding model can't load, it says so in the log and lets the regex decide (fail open to the regex,
which is still on).
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache

import numpy as np
import yaml

from app.safety import SafetyHit, check
from app.settings import ROOT

log = logging.getLogger(__name__)
CONFIG = ROOT / "config/safety_semantic.yaml"


@lru_cache(maxsize=1)
def _config() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def _embed(texts: list[str]) -> np.ndarray:
    from app.models.embeddings import embed

    return embed(texts)


@lru_cache(maxsize=1)
def _references() -> tuple[np.ndarray, list[str], np.ndarray]:
    cfg = _config()
    pairs = [(cat, t) for cat, texts in cfg["hazard"].items() for t in texts]
    hazards = _embed([t for _, t in pairs])
    safe = _embed(list(cfg["safe"]))
    return hazards, [c for c, _ in pairs], safe


@lru_cache(maxsize=256)
def vector(text: str) -> np.ndarray:
    """One text's embedding, cached: the danger net and app/intent.py embed the same question."""
    return _embed([text])[0]


def scores(text: str) -> tuple[float, float, str]:
    """(closest hazard similarity, closest safe similarity, that hazard's category)."""
    hazards, cats, safe = _references()
    v = vector(text)
    h = hazards @ v
    i = int(np.argmax(h))
    return float(h[i]), float(np.max(safe @ v)), cats[i]


def check_meaning(text: str, margin: float | None = None, min_hazard: float | None = None) -> SafetyHit | None:
    """A SafetyHit when the text means something dangerous, else None. Empty text is never a hit."""
    if not text.strip() or os.environ.get("HOMEFIX_SAFETY_MEANING") == "off":  # off: subprocess tests only
        return None
    cfg = _config()
    margin = cfg["margin"] if margin is None else margin
    min_hazard = cfg["min_hazard"] if min_hazard is None else min_hazard
    try:
        haz, safe, cat = scores(text)
    except Exception as e:  # noqa: BLE001 - the regex is still on; never block a question on a load error
        log.warning("meaning-based safety check unavailable: %s", e)
        return None
    if haz >= min_hazard and haz - safe >= margin:
        return SafetyHit(cat, f"meaning: {haz:.2f} vs safe {safe:.2f}")
    return None


def check_all(text: str) -> SafetyHit | None:
    """The regex first; the meaning net only when the regex found nothing. Nothing can clear a regex stop."""
    return check(text) or check_meaning(text)


def warm() -> None:
    """Load the embedding model and the reference vectors now, so the first question doesn't wait ~9 s."""
    try:
        scores("warm up")
    except Exception as e:  # noqa: BLE001
        log.warning("couldn't warm the meaning-based safety check: %s", e)
