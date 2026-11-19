from pathlib import Path

import pytest

from app.contracts import Attachment
from app.router import route


def att(kind, name="f"):
    return Attachment(Path(name), kind, name)


@pytest.mark.parametrize("message,kinds,manual,modality,qtype", [
    ("How many mugs are on the shelf?", ["image"], None, "image", "count"),
    ("", ["image"], None, "image", "describe"),
    ("What does the display say?", ["image"], None, "image", "read"),
    ("Is this mold?", ["image"], None, "image", "qa"),
    ("What does the error code mean?", ["image"], "washer", "homefix", "manual_lookup"),
    ("Which way is the drum turning?", ["video"], None, "video", "motion"),
    ("", ["video"], None, "video", "describe"),
    ("What did she say?", ["audio"], None, "audio", "speech"),
    ("What is this beeping sound?", ["audio"], None, "audio", "sound"),
    ("", ["audio"], None, "audio", "none"),
    ("When should I clean the filter?", ["document"], None, "text", "doc_qa"),
    ("When should I clean the filter?", [], "washer", "text", "doc_qa"),
    ("Write a function that averages watts per hour", ["data"], None, "code", "code_gen"),
    ("write a python script to sum a list", [], None, "code", "code_gen"),
    ("smoke detector keeps chirping", [], "washer", "text", "doc_qa"),
])
def test_route(message, kinds, manual, modality, qtype):
    r = route(message, [att(k) for k in kinds], manual)
    assert (r.modality, r.question_type) == (modality, qtype)
    assert r.refusal is None


def test_document_without_question():
    r = route("", [att("document")], None)
    assert r.refusal.message == "Ask a question about the document."
    assert r.refusal.reason == "empty_input"
    assert (r.modality, r.question_type) == ("none", "none")


def test_no_document():
    r = route("how do I unclog a drain", [], None)
    assert r.refusal.reason == "no_document"
    assert r.modality == "none"


def test_mixed_kinds_first_wins():
    r = route("what is this", [att("audio"), att("image")], None)
    assert r.modality == "audio"
    assert r.note == "Only the first file was used."


def test_four_images_no_note():
    r = route("what is this", [att("image", f"i{n}") for n in range(4)], None)
    assert r.modality == "image"
    assert r.note is None


def test_two_audio_notes_first_only():
    r = route("", [att("audio"), att("audio")], None)
    assert r.modality == "audio"
    assert r.note == "Only the first file was used."


def test_data_anywhere_goes_to_code():
    r = route("hi", [att("image"), att("data")], None)
    assert r.modality == "code"


def test_manual_with_two_images_is_not_manual_lookup():
    r = route("hi", [att("image"), att("image")], "washer")
    assert r.modality == "image"
