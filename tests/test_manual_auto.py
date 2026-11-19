"""manual_id="auto": the UI's default. A manual is used when the question is about an appliance, and a
manual with a junk PDF title gets a readable name. Invented manuals only."""

import pytest

from app import orchestrate
from app.contracts import Attachment
from app.pipelines import homefix, text
from tests import media_fixtures as mf


@pytest.fixture
def manuals(tmp_path, monkeypatch):
    monkeypatch.setattr(text, "MANUALS_DIR", tmp_path)

    def add(stem, title=None):
        p = mf.make_pdf(tmp_path / f"{stem}.pdf", ["Clean the filter monthly."])
        if title is not None:
            import pymupdf
            with pymupdf.open(p) as d:
                d.set_metadata({"title": title})
                d.save(tmp_path / "x.pdf")
            (tmp_path / "x.pdf").replace(p)
        return stem
    return add


def img(tmp_path):
    return [Attachment(tmp_path / "a.jpg", "image", "a.jpg")]


def test_auto_uses_the_manual_for_an_appliance_photo(manuals, tmp_path):
    manuals("washer_acme_w100")
    assert orchestrate.resolve_manual("auto", "My washer shows this code. What should I do?", img(tmp_path)) \
        == "washer_acme_w100"
    assert orchestrate.resolve_manual("auto", "What does this error mean?", img(tmp_path)) == "washer_acme_w100"


def test_auto_leaves_other_photos_alone(manuals, tmp_path):
    manuals("washer_acme_w100")
    assert orchestrate.resolve_manual("auto", "How many mugs are on the shelf?", img(tmp_path)) is None
    assert orchestrate.resolve_manual("auto", "", img(tmp_path)) is None


def test_auto_answers_text_questions_from_the_manual(manuals):
    manuals("washer_acme_w100")
    assert orchestrate.resolve_manual("auto", "How do I clean the drain filter?", []) == "washer_acme_w100"


def test_auto_never_for_sound_video_or_an_attached_document(manuals, tmp_path):
    manuals("washer_acme_w100")
    for kind, name in [("audio", "b.wav"), ("video", "c.mp4"), ("document", "lease.pdf")]:
        assert orchestrate.resolve_manual("auto", "what is this washer doing?",
                                          [Attachment(tmp_path / name, kind, name)]) is None


def test_auto_picks_the_manual_named_in_the_question(manuals):
    manuals("dryer_acme_d1")
    manuals("washer_acme_w100")
    assert orchestrate.resolve_manual("auto", "my washer won't drain", []) == "washer_acme_w100"
    assert orchestrate.resolve_manual("auto", "the dryer is too hot", []) == "dryer_acme_d1"


def test_auto_without_manuals_and_explicit_choices(manuals, tmp_path):
    assert orchestrate.resolve_manual("auto", "my washer won't drain", []) is None
    manuals("washer_acme_w100")
    assert orchestrate.resolve_manual("washer_acme_w100", "How many mugs?", img(tmp_path)) == "washer_acme_w100"
    assert orchestrate.resolve_manual(None, "my washer won't drain", []) is None


def test_handle_says_which_manual_it_used(manuals, ctx_lite, monkeypatch):
    manuals("washer_acme_w100")
    seen = {}

    def fake_run(req, ctx):
        seen["manual_id"] = req.manual_id
        return iter(())
    monkeypatch.setattr("app.pipelines.text.run", fake_run)
    events = list(orchestrate.handle("How do I clean the filter?", [], "auto", ctx_lite))
    assert seen["manual_id"] == "washer_acme_w100"
    assert any(getattr(e, "detail", None) == "Using the manual: Washer ACME W100" for e in events)


@pytest.mark.parametrize(("stem", "title", "shown"), [
    ("washer_acme_w100", "Title", "Washer ACME W100"),
    ("washer_acme_w100", "", "Washer ACME W100"),
    ("washer_acme_w100", "Microsoft Word - manual.docx", "Washer ACME W100"),
    ("dryer-lg-dlex", "untitled", "Dryer LG DLEX"),
    ("washer_acme_w100", "ACME W100 User Manual", "ACME W100 User Manual"),
])
def test_manual_titles_are_readable(manuals, stem, title, shown):
    manuals(stem, title)
    assert [m["title"] for m in homefix.list_manuals()] == [shown]
