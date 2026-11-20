"""When HomeFix asks instead of guessing.

The 2B vision model can't tell when it is guessing (asked to "reply ASK: ..." when unsure, it does so for every
question), so the decision is made here, by rules that tests can pin down. The model only reads the display.

- A vague question about a photo ("What is this?", "What does this mean?", or no question at all) with no error
  code on it: say what HomeFix could read and ask what the person wants to know.
- A specific photo question the model can't answer ("I can't tell."): ask for what's missing.
- More than one manual could answer: ask which appliance it is, with the manuals as one-click replies.
"""

from __future__ import annotations

import re

from app.contracts import MESSAGES, Clarify, ClarifyOption

# Words that carry no subject. A question made only of these doesn't say what the person wants to know.
_EMPTY_WORDS = frozenset(["a", "an", "the", "and", "or", "to", "of", "for", "on", "in", "at", "is", "it", "its", "it's", "my", "me", "i", "you", "your", "this", "that", "these", "those", "what", "what's", "whats", "how", "do", "does", "did", "can", "could", "should", "will", "would", "with", "from", "who", "when", "where", "why", "which", "are", "was", "were", "be", "been", "has", "have", "there", "here", "mean", "means", "meaning", "wrong", "something", "anything", "going", "happening", "normal", "fine", "ok", "okay", "right", "broken", "problem", "issue", "help", "please", "hi", "hey", "tell", "about", "see", "look", "know", "need", "thing", "things", "photo", "picture", "pic", "image", "display", "screen", "showing", "shows", "show", "check", "any", "all", "just", "so", "now"])

_CODE = re.compile(r"\b[A-Z]{1,3}-?\d{1,3}\b")
# Upper-case labels of letters only, one or more words: "COOKTOP ON", "LOCKED", "SET".
_LABEL = re.compile(r"\b[A-Z]{2,}(?:[ \t]+[A-Z]{2,})*\b")
MAX_LABELS = 2


def is_vague(message: str) -> bool:
    """True when the question has no subject of its own (only words like what / this / mean / wrong)."""
    words = re.findall(r"[a-z0-9']+", message.lower())
    return not [w for w in words if w not in _EMPTY_WORDS]


_CANT = MESSAGES["cant_tell"].lower().rstrip(".")


def clean_reading(reading: str) -> str:
    """The reading without what the model added about itself: an "I can't tell." line or ending."""
    lines = []
    for ln in reading.strip().splitlines():
        cut = ln.lower().find(_CANT)
        lines.append(ln if cut < 0 else ln[:cut].rstrip())
    return "\n".join(ln for ln in lines if ln.strip()).strip()


def _readable(reading: str) -> bool:
    return bool(clean_reading(reading))


def looks_like_display(reading: str) -> bool:
    """A readable display or panel: words with at least one number (a code, a time, a temperature)."""
    return _readable(reading) and any(ch.isdigit() for ch in reading)


def seen_items(reading: str) -> list[str]:
    """Things worth asking about in what was read: an error code first, else upper-case labels."""
    if not _readable(reading):
        return []
    code = _CODE.search(reading)
    if code:
        return [code.group(0)]
    out: list[str] = []
    for m in _LABEL.finditer(reading):
        if m.group(0) not in out:
            out.append(m.group(0))
    return out[:MAX_LABELS]


def photo_clarify(reading: str) -> Clarify:
    """The question back for a vague photo question. Every reply offered is specific, so it can't loop."""
    seen = clean_reading(reading) or None
    items = seen_items(reading)
    options = []
    for item in items:
        if _CODE.fullmatch(item):
            options.append(ClarifyOption(label=f"What does error code {item} mean?",
                                         message=f"What does error code {item} mean?"))
        else:
            options.append(ClarifyOption(label=f"What does “{item}” mean?",
                                         message=f'What does "{item}" mean?'))
    if seen:
        options.append(ClarifyOption(label="Read everything on it", message="What does the display say?"))
    options.append(ClarifyOption(label="Describe the photo", message="Describe the photo."))
    if not seen:
        question = ("I couldn't read any words or numbers in this photo. What would you like to know? "
                    "Tell me what the appliance is and what you noticed.")
    elif items and _CODE.fullmatch(items[0]):
        question = "What would you like to know about this photo? Tell me which appliance it is if you can."
    else:
        question = ("I don't see an error code. What would you like to know? "
                    "Tell me which appliance this is and what you noticed, or pick one below.")
    return Clarify(question=question, seen=seen, options=options)


_SAYS_CODE = re.compile(r"\b(code|error|err)\b", re.IGNORECASE)


def mentions_a_code(message: str) -> bool:
    return bool(_SAYS_CODE.search(message))


def code_clarify(reading: str) -> Clarify:
    """The person says there's a code, but none could be read. Ask for it rather than answer something else."""
    seen = clean_reading(reading) or None
    return Clarify(
        question=("I couldn't find an error code in this photo. Which code does it show? Type it, like E24, "
                  "or try a photo straight on."),
        seen=seen,
        options=[ClarifyOption(label="Read everything on it", message="What does the display say?"),
                 ClarifyOption(label="Describe the photo", message="Describe the photo.")],
    )


def cant_tell_clarify(seen: str | None = None) -> Clarify:
    """The photo doesn't show the answer. Starts with "I can't tell" so it still reads as an honest no."""
    return Clarify(
        question=("I can't tell that from the photo alone. What else can you tell me? "
                  "For example, which appliance this is, or what you did just before."),
        seen=clean_reading(seen) or None if seen else None,
        options=[ClarifyOption(label="Read everything on it", message="What does the display say?"),
                 ClarifyOption(label="Describe the photo", message="Describe the photo.")],
    )


def manual_clarify(message: str, manuals: list[dict], code: str | None = None) -> Clarify:
    """Ask which appliance it is. Each reply re-asks the same question with that manual picked."""
    what = f"Several manuals mention {code}." if code else "More than one manual could answer this."
    return Clarify(
        question=f"{what} Which appliance is it?",
        seen=code,
        options=[ClarifyOption(label=m["title"], message=message, manual_id=m["id"]) for m in manuals],
    )
