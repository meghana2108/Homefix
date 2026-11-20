import pymupdf

from app.contracts import (
    Attachment,
    Citation,
    Clarify,
    Final,
    PipelineRequest,
    Refusal,
    Status,
    Token,
)
from app.pipelines import homefix, text

PAGES = [
    "Error E21 means the water did not drain. Clean the drain pump filter every month.",
    "To level the washer, turn the front feet. Use a spirit level on the lid.",
]


def make(tmp_path, monkeypatch):
    monkeypatch.setattr(text, "MANUALS_DIR", tmp_path)
    d = pymupdf.open()
    for t in PAGES:
        d.new_page().insert_text((72, 72), t)
    d.save(tmp_path / "w1.pdf")


def req(tmp_path):
    img = Attachment(path=tmp_path / "x.jpg", kind="image", original_name="x.jpg")
    return PipelineRequest("what does this mean?", [img], "manual_lookup", "w1")


def test_read_display_code():
    assert homefix.read_display_code("The display shows E21.") == "E21"
    assert homefix.read_display_code("Code: F-05") == "F-05"
    assert homefix.read_display_code("I can't tell.") is None


def test_code_then_manual_citation(fake_brain, ctx_full, tmp_path, monkeypatch):
    make(tmp_path, monkeypatch)
    fake_brain("None", "None", "E21", '{"answer":"The water did not drain.",'
               '"quote":"Error E21 means the water did not drain","page":1}')
    ev = list(homefix.run(req(tmp_path), ctx_full))
    assert any(isinstance(e, Status) and e.detail == "found E21" for e in ev)
    assert next(e for e in ev if isinstance(e, Citation)).page == 1
    assert isinstance(ev[-1], Final) and ev[-1].modality == "homefix"
    assert ev[-1].question_type == "manual_lookup"


def test_cant_read_code_asks_instead_of_blaming_the_photo(fake_brain, ctx_full, tmp_path, monkeypatch):
    make(tmp_path, monkeypatch)
    fake_brain("None", "None", "I can't tell.")
    ev = list(homefix.run(req(tmp_path), ctx_full))
    c = next(e for e in ev if isinstance(e, Clarify))
    assert c.seen is None and "couldn't read" in c.question
    assert ev[-1].answer == c.question and ev[-1].modality == "homefix"  # nothing read, so just the question


def test_no_tokens_from_display_read(fake_brain, ctx_full, tmp_path, monkeypatch):
    make(tmp_path, monkeypatch)
    fake_brain("None", "None", "The display shows E21.", '{"answer":"Clean the drain pump filter.",'
               '"quote":"Clean the drain pump filter every month","page":1}')
    ev = list(homefix.run(req(tmp_path), ctx_full))
    assert not any(isinstance(e, Token) for e in ev)


def test_refused_lookup_has_no_tokens(fake_brain, ctx_full, tmp_path, monkeypatch):
    make(tmp_path, monkeypatch)
    fake_brain("None", "None", "The display shows E21.", '{"answer":null,"quote":null,"page":null}')
    ev = list(homefix.run(req(tmp_path), ctx_full))
    assert not any(isinstance(e, Token) for e in ev)
    assert isinstance(ev[-2], Refusal) and ev[-2].reason == "not_in_document"
    assert ev[-1].answer == ""


def test_code_with_words_before():
    assert homefix.read_display_code("In 2 lines the display shows E21") == "E21"
