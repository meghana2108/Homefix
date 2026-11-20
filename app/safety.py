"""Deterministic safety pre-filter. Runs on every message before any model."""
from __future__ import annotations

import re
from dataclasses import dataclass

import yaml

from app.contracts import Refusal, SoundLabel
from app.settings import ROOT

with open(ROOT / "config/safety_rules.yaml", encoding="utf-8") as _f:
    _RULES = yaml.safe_load(_f)

SAFETY_MESSAGE: str = _RULES["message"]  # fallback for a category with no message of its own
_MESSAGES: dict[str, str] = _RULES.get("messages", {})
ALARM_LABELS: frozenset[str] = frozenset({
    "smoke alarm beeping loudly",
    "carbon monoxide alarm",
    "smoke detector, smoke alarm",
    "fire alarm",
})

def _compile(section: dict) -> list[tuple[str, list[tuple[str, re.Pattern]]]]:
    return [
        (cat, [(p, re.compile(p, re.IGNORECASE)) for p in pats])
        for cat, pats in section.items()
    ]


_ALARM_ACTIVE = _compile(_RULES.get("alarm_active", {}))
_DANGER = _compile(_RULES["patterns"])
_OBSERVED = _compile(_RULES.get("observed", {}))
_DEVICE_NAMES = [re.compile(p, re.IGNORECASE) for p in _RULES.get("device_names", [])]
_BENIGN = [re.compile(p, re.IGNORECASE) for p in _RULES.get("benign", [])]


@dataclass
class SafetyHit:
    category: str
    pattern: str


def check(text: str) -> SafetyHit | None:
    text = text.lower()
    for cat, pats in _ALARM_ACTIVE:
        for raw, rx in pats:
            if rx.search(text):
                return SafetyHit(cat, raw)
    for rx in _DEVICE_NAMES:
        text = rx.sub(" device ", text)
    for rx in _BENIGN:
        text = rx.sub(" ", text)
    for cat, pats in _DANGER:
        for raw, rx in pats:
            if rx.search(text):
                return SafetyHit(cat, raw)
    return None


def message_for(category: str) -> str:
    """The fixed message for one kind of danger (gas never says to touch a switch), else the general one."""
    return _MESSAGES.get(category, SAFETY_MESSAGE)


def check_observation(text: str) -> SafetyHit | None:
    """Danger the vision model says it sees ("burn marks", "exposed wiring", "water near the outlet")."""
    for cat, pats in _OBSERVED:
        for raw, rx in pats:
            if rx.search(text):
                return SafetyHit(cat, raw)
    return None


def refusal_for(hit: SafetyHit) -> Refusal:
    return Refusal(reason="safety", message=message_for(hit.category), category=hit.category)


def check_sound(labels: list[SoundLabel], min_score: float) -> SafetyHit | None:
    if not labels:
        return None
    top = labels[0]
    if top.label in ALARM_LABELS and top.score >= min_score:
        return SafetyHit("co" if top.label == "carbon monoxide alarm" else "smoke_fire", top.label)
    return None
