"""Prompt wording for the image pipeline (video imports the count/read helpers too)."""

from __future__ import annotations

import re

from app.contracts import MESSAGES
from app.numbers import first_int

_THING = re.compile(r"\bhow many\s+(.+?)(?:\s+(?:are|is|do|does|did|can|could|were|was|in|on|at|there|you)\b|[?.!,]|$)",
                    re.IGNORECASE)
READ_PROMPT = "Read the text exactly as written. If you can't read it, reply exactly: I can't tell."
DESCRIBE_PROMPT = "Describe the image in one paragraph of at most 80 words."


def count_prompt(message: str) -> str:
    m = _THING.search(message)
    thing = m.group(1).strip() if m and m.group(1).strip() else "objects"
    return (f"Count the {thing}. Reply with the number first as digits, then one short sentence. "
            "If the image is too blurry to count, reply exactly: I can't tell.")


def qa_prompt(message: str) -> str:
    return (f"{message}\nAnswer in one paragraph of at most 80 words. "
            f"If the image doesn't show it, reply exactly: {MESSAGES['cant_tell']}")


def display_prompt(reading: str, message: str) -> str:
    """Answer a question about a display from its words alone, no image. Given the photo too, the 2B model
    guesses ("the digital timer shows 8:32" for a clock); given only the words, it says "I can't tell"."""
    return (f"The display in this photo reads:\n{reading.strip()}\n\nQuestion: {message}\n"
            "Answer in one or two sentences using only what is written on the display. Button names (like Start, "
            "Cancel or Oven Light) are not messages. Don't add anything the words don't say. "
            f"If the words don't answer the question, reply exactly: {MESSAGES['cant_tell']}")


def force_number_first(answer: str) -> str:
    text = answer.strip()
    if not text or text[0].isdigit() or text.lower().startswith(MESSAGES["cant_tell"].lower().rstrip(".")):
        return text
    n = first_int(text)
    return f"{n}. {text}" if n is not None else text
