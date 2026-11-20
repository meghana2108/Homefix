"""Rule-based router: picks the pipeline and question type with plain rules, no model call."""

from __future__ import annotations

import re
from collections.abc import Callable

from app.contracts import MESSAGES, Attachment, QuestionType, Refusal, Route

_F = re.IGNORECASE
CODE_GEN = re.compile(r"\b(write|create|implement|generate)\b.{0,40}\b(function|script|code|program|class)\b", _F)
PYTHON = re.compile(r"\bpython\b|\bdef \w+\(", _F)
COUNT = re.compile(r"\bhow many\b|\bcount\b|\bnumber of\b", _F)
READ = re.compile(r"\b(read|say|says|written|text|code|display|label|sign|error)\b", _F)
DESCRIBE = re.compile(r"\bdescribe|what('s| is) (in|this)\b", _F)
MOTION = re.compile(r"\b(direction|moving|move|moves|turn|turning|spin|spinning|left|right|toward|away)\b", _F)
SPEECH = re.compile(r"\b(say|said|says|transcribe|transcript|words|talking)\b", _F)
SOUND = re.compile(r"\b(sound\w*|noise\w*|beep\w*|hear|hearing|chirp\w*|drip\w*|buzz\w*|hum|humming|hums|whistl\w*|click\w*|rattl\w*|hiss\w*|squeal\w*|bang\w*|ring\w*|alarm\w*)\b", _F)

Rule = Callable[[str, list[Attachment], "str | None"], "Route | None"]


def _refuse(reason: str, message: str) -> Route:
    return Route("none", "none", refusal=Refusal(reason=reason, message=message))


def rule_manual_image(message, attachments, manual_id):
    if manual_id and len(attachments) == 1 and attachments[0].kind == "image":
        return Route("homefix", "manual_lookup")
    return None


def rule_code(message, attachments, manual_id):
    if any(a.kind == "data" for a in attachments):
        return Route("code", "code_gen")
    if not attachments and (CODE_GEN.search(message) or PYTHON.search(message)):
        return Route("code", "code_gen")
    return None


def _visual_type(message: str, video: bool) -> QuestionType:
    if COUNT.search(message):
        return "count"
    if READ.search(message):
        return "read"
    if video and MOTION.search(message):
        return "motion"
    if not video and DESCRIBE.search(message):
        return "describe"
    if not message:
        return "describe"
    return "qa"


def _audio_type(message: str) -> QuestionType:
    if SPEECH.search(message):
        return "speech"
    if SOUND.search(message):
        return "sound"
    return "none"


def rule_attachment(message, attachments, manual_id):
    if not attachments:
        return None
    kind = attachments[0].kind
    all_images = all(a.kind == "image" for a in attachments)
    note = None if (len(attachments) == 1 or all_images) else MESSAGES["first_file_only"]
    if kind == "image":
        return Route("image", _visual_type(message, video=False), note=note)
    if kind == "video":
        return Route("video", _visual_type(message, video=True), note=note)
    if kind == "audio":
        return Route("audio", _audio_type(message), note=note)
    if kind == "document":
        if not message:
            return _refuse("empty_input", MESSAGES["empty_doc_question"])
        return Route("text", "doc_qa", note=note)
    return None


def rule_manual_text(message, attachments, manual_id):
    if not attachments and manual_id:
        return Route("text", "doc_qa")
    return None


def rule_no_document(message, attachments, manual_id):
    if not attachments:
        return _refuse("no_document", MESSAGES["no_document"])
    return None


RULES: list[Rule] = [rule_manual_image, rule_code, rule_attachment, rule_manual_text,
                     rule_no_document]


def route(message: str, attachments: list[Attachment], manual_id: str | None) -> Route:
    message = message.strip()
    for rule in RULES:
        result = rule(message, attachments, manual_id)
        if result is not None:
            return result
    return _refuse("no_document", MESSAGES["no_document"])
