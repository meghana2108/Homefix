"""HomeFix asks instead of guessing: a vague question about a photo, a photo it can't answer, or a question that
more than one manual could answer gets a `clarify` event with what HomeFix saw and one-click replies.
Invented displays and manuals only."""

import pymupdf
import pytest

from app import clarify, orchestrate, prompts
from app.contracts import (
    Attachment,
    Citation,
    Clarify,
    Final,
    PipelineRequest,
    Refusal,
    Status,
)
from app.pipelines import homefix, image, text
from tests.media_fixtures import make_jpeg

COOKTOP_READING = "8:32 COOKTOP ON Oven Light Start | Cancel Lock Control Hold 3 Sec"


@pytest.mark.parametrize("q", ["", "What is this?", "what does this mean?", "Is something wrong?", "help",
                               "What's going on here?", "Is this normal?", "what does the display mean"])
def test_vague_questions(q):
    assert clarify.is_vague(q)


@pytest.mark.parametrize("q", ["Is the oven on?", "How long is left on the timer?", "Describe the photo.",
                               'What does "COOKTOP ON" mean?', "What does this mean? It's the clock on my cooktop",
                               "What does error code E21 mean?"])
def test_specific_questions(q):
    assert not clarify.is_vague(q)


def test_seen_items_picks_labels_and_codes_not_buttons():
    assert clarify.seen_items(COOKTOP_READING) == ["COOKTOP ON"]
    assert clarify.seen_items("E21 Spin Rinse") == ["E21"]
    assert clarify.seen_items("I can't tell.") == []
    assert clarify.seen_items("TEMP\nCOOL\n80\nF\nHunter") == ["TEMP", "COOL"]  # a label never spans lines


def test_photo_clarify_shows_what_it_read_and_offers_replies():
    c = clarify.photo_clarify(COOKTOP_READING)
    assert c.seen == COOKTOP_READING
    assert "error code" in c.question
    labels = [o.label for o in c.options]
    assert labels[0] == "What does “COOKTOP ON” mean?"
    assert "Read everything on it" in labels and "Describe the photo" in labels
    assert all(o.message and o.manual_id is None for o in c.options)
    # every one-click reply is specific, so it can't loop back into another clarify
    assert not any(clarify.is_vague(o.message) for o in c.options)


def test_one_click_replies_route_to_the_right_kind_of_answer():
    """With no manual (or before the UI has loaded the shelf), "display" in a reply would make it a read."""
    from app.router import route
    att = [Attachment(None, "image", "p.jpg")]
    kinds = {o.label: route(o.message, att, None).question_type for o in clarify.photo_clarify(COOKTOP_READING).options}
    assert kinds == {"What does “COOKTOP ON” mean?": "qa", "Read everything on it": "read",
                     "Describe the photo": "describe"}


def test_a_trailing_cant_tell_is_not_shown_as_something_read():
    c = clarify.photo_clarify("832\nCOOKTOP ON\nLight Start Cancel Lock\nI can't tell.")
    assert c.seen == "832\nCOOKTOP ON\nLight Start Cancel Lock"


def test_photo_clarify_when_nothing_is_readable():
    c = clarify.photo_clarify("I can't tell.")
    assert c.seen is None
    assert "couldn't read" in c.question


def img_req(tmp_path, message, qtype="qa", manual_id=None):
    att = Attachment(make_jpeg(tmp_path / "p.jpg", circles=1), "image", "p.jpg")
    return PipelineRequest(message, [att], qtype, manual_id)


def test_image_vague_question_asks_instead_of_guessing(ctx_full, fake_brain, tmp_path):
    fake_brain("None", "None", COOKTOP_READING)  # two clean danger looks, then the reading
    ev = list(image.run(img_req(tmp_path, "What is this?", "describe"), ctx_full))
    c = next(e for e in ev if isinstance(e, Clarify))
    assert c.seen == COOKTOP_READING
    assert len(fake_brain.calls) == 3 and "Read the text" in fake_brain.calls[2]["messages"][-1]["content"]
    assert isinstance(ev[-1], Final) and ev[-1].answer.startswith(c.question)
    assert ev[-1].answer.endswith("What I could read: 8:32 COOKTOP ON Oven Light Start | Cancel Lock Control Hold 3 Sec.")


def test_image_vague_question_about_a_scene_is_described_not_asked(ctx_full, fake_brain, tmp_path):
    """No display in the photo (nothing with numbers to misread): "What is this?" wants a description."""
    fake_brain("None", "None", "I can't tell.", "A kitchen counter with two mugs.")
    ev = list(image.run(img_req(tmp_path, "What's in this photo?", "describe"), ctx_full))
    assert not any(isinstance(e, Clarify) for e in ev)
    assert ev[-1].answer == "A kitchen counter with two mugs."
    assert fake_brain.calls[3]["messages"][-1]["content"] == prompts.DESCRIBE_PROMPT


def test_image_empty_message_asks_too(ctx_full, fake_brain, tmp_path):
    fake_brain("None", "None", COOKTOP_READING)
    ev = list(image.run(img_req(tmp_path, "", "describe"), ctx_full))
    assert any(isinstance(e, Clarify) for e in ev)


def test_image_display_question_is_answered_from_its_words_only(ctx_full, fake_brain, tmp_path):
    fake_brain(COOKTOP_READING, COOKTOP_READING, "COOKTOP ON means the cooktop is turned on.")  # 2 reads agree
    ev = list(image.run(img_req(tmp_path, 'What does "COOKTOP ON" mean?'), ctx_full))
    assert not any(isinstance(e, Clarify) for e in ev)
    assert ev[-1].answer == "COOKTOP ON means the cooktop is turned on."
    second = fake_brain.calls[2]
    assert second["images"] is None  # words only: with the photo the model guesses "a timer"
    assert COOKTOP_READING in second["messages"][-1]["content"]


def test_image_non_display_question_still_sees_the_photo(ctx_full, fake_brain, tmp_path):
    fake_brain("I can't tell.", "The mug is blue.")
    ev = list(image.run(img_req(tmp_path, "What color is the mug?"), ctx_full))
    assert ev[-1].answer == "The mug is blue."
    assert fake_brain.calls[1]["images"]


def test_image_cant_tell_becomes_a_question_back(ctx_full, fake_brain, tmp_path):
    fake_brain(COOKTOP_READING, COOKTOP_READING, "I can't tell.")
    ev = list(image.run(img_req(tmp_path, "How long is left on the timer?"), ctx_full))
    c = next(e for e in ev if isinstance(e, Clarify))
    assert c.question.startswith("I can't tell that from the photo alone.")
    assert c.seen == COOKTOP_READING
    assert ev[-1].answer.startswith("I can't tell")  # still an honest no for graders


def test_an_answer_that_only_repeats_the_display_is_not_an_answer(ctx_full, fake_brain, tmp_path):
    fake_brain(COOKTOP_READING, COOKTOP_READING, "8:32\nCOOKTOP ON\nOven Light\nStart | Cancel\nLock Control\nHold 3 Sec")
    ev = list(image.run(img_req(tmp_path, 'What does "COOKTOP ON" mean?'), ctx_full))
    assert any(isinstance(e, Clarify) for e in ev)


def test_a_short_answer_from_the_display_is_kept(ctx_full, fake_brain, tmp_path):
    fake_brain(COOKTOP_READING, COOKTOP_READING, "8:32")
    ev = list(image.run(img_req(tmp_path, "What time does it show?"), ctx_full))
    assert ev[-1].answer == "8:32"


def test_an_answer_that_ends_in_cant_tell_is_not_shown_as_an_answer(ctx_full, fake_brain, tmp_path):
    fake_brain(COOKTOP_READING, COOKTOP_READING, "The oven is on. I can't tell.")
    ev = list(image.run(img_req(tmp_path, "Is the oven on?"), ctx_full))
    assert any(isinstance(e, Clarify) for e in ev)


def test_a_reading_with_a_trailing_cant_tell_keeps_only_the_reading(ctx_full, fake_brain, tmp_path):
    fake_brain("EASY SET Thermostat CAUTION: RISK OF SCALDING I can't tell.")
    ev = list(image.run(img_req(tmp_path, "What does the label say?", "read"), ctx_full))
    assert ev[-1].answer == "EASY SET Thermostat CAUTION: RISK OF SCALDING"


def test_count_and_read_never_ask(ctx_full, fake_brain, tmp_path):
    fake_brain("I can't tell.")
    ev = list(image.run(img_req(tmp_path, "How many burners?", "count"), ctx_full))
    assert not any(isinstance(e, Clarify) for e in ev)


# ---- the manual path ----

def shelf(tmp_path, monkeypatch, manuals: dict[str, list[str]]):
    monkeypatch.setattr(text, "MANUALS_DIR", tmp_path)
    for stem, pages in manuals.items():
        d = pymupdf.open()
        for t in pages:
            d.new_page().insert_text((72, 72), t)
        d.save(tmp_path / f"{stem}.pdf")


def test_manual_photo_without_a_code_asks_when_vague(ctx_full, fake_brain, tmp_path, monkeypatch):
    shelf(tmp_path, monkeypatch, {"w1": ["E21 means the washer cannot drain."]})
    fake_brain("None", "None", COOKTOP_READING, COOKTOP_READING)
    ev = list(homefix.run(img_req(tmp_path, "What does this mean?", "manual_lookup", "w1"), ctx_full))
    c = next(e for e in ev if isinstance(e, Clarify))
    assert c.seen == COOKTOP_READING
    assert ev[-1].answer.startswith(c.question) and "sharper photo" not in c.question


def test_manual_photo_without_a_code_answers_a_specific_question_from_the_photo(ctx_full, fake_brain, tmp_path,
                                                                                    monkeypatch):
    shelf(tmp_path, monkeypatch, {"w1": ["E21 means the washer cannot drain."]})
    fake_brain(COOKTOP_READING, COOKTOP_READING, '{"answer":null,"quote":null,"page":null}',  # the manual: nothing
               "The display says COOKTOP ON, so a cooktop burner is on.")
    ev = list(homefix.run(img_req(tmp_path, 'What does "COOKTOP ON" mean?', "manual_lookup", "w1"), ctx_full))
    assert not any(isinstance(e, Clarify | Citation) for e in ev)
    assert ev[-1].answer.startswith("The display says COOKTOP ON")
    assert ev[-1].modality == "image" and ev[-1].question_type == "qa"


def test_question_says_there_is_a_code_but_none_is_read_asks_for_it(ctx_full, fake_brain, tmp_path, monkeypatch):
    shelf(tmp_path, monkeypatch, {"w1": ["E24 means the dishwasher cannot drain."]})
    fake_brain("624 h min Eco Auto Rinse Start", "624 h min Eco Auto Rinse Start")
    ev = list(homefix.run(img_req(tmp_path, "My dishwasher shows this code. What should I do?", "manual_lookup",
                                  "w1"), ctx_full))
    c = next(e for e in ev if isinstance(e, Clarify))
    assert "Which code" in c.question and c.seen == "624 h min Eco Auto Rinse Start"


def test_a_code_typed_in_the_reply_is_used_when_the_photo_has_none(ctx_full, fake_brain, tmp_path, monkeypatch):
    shelf(tmp_path, monkeypatch, {"w1": ["E24 means the dishwasher cannot drain."]})
    fake_brain("624 h min", '{"answer":"It cannot drain.","quote":"E24 means the dishwasher cannot drain","page":1}')
    ev = list(homefix.run(img_req(tmp_path, "My dishwasher shows this code. What should I do?\nIt says E24",
                                  "manual_lookup", "w1"), ctx_full))
    assert any(isinstance(e, Status) and e.detail == "found E24" for e in ev)
    assert any(isinstance(e, Citation) for e in ev)


def test_auto_manual_photo_finds_the_manual_by_its_code(ctx_full, fake_brain, tmp_path, monkeypatch):
    shelf(tmp_path, monkeypatch, {"guide_a": ["Heating: call the office."],
                                  "guide_b": ["E24 means the dishwasher cannot drain. Clean the filter."]})
    fake_brain("E24", "E24", '{"answer":"It cannot drain.","quote":"E24 means the dishwasher cannot drain","page":1}')
    ev = list(homefix.run(img_req(tmp_path, "What does this code mean?", "manual_lookup", "auto"), ctx_full))
    assert any(isinstance(e, Status) and (e.detail or "").startswith("Using the manual: Guide B") for e in ev)
    assert next(e for e in ev if isinstance(e, Citation)).source == "guide_b.pdf"


def test_auto_manual_photo_asks_which_appliance_when_two_manuals_have_the_code(ctx_full, fake_brain, tmp_path,
                                                                                 monkeypatch):
    shelf(tmp_path, monkeypatch, {"washer_a": ["E21 means the washer cannot drain."],
                                  "oven_b": ["E21 means the oven sensor failed."]})
    fake_brain("E21", "E21")
    ev = list(homefix.run(img_req(tmp_path, "What does this code mean?", "manual_lookup", "auto"), ctx_full))
    c = next(e for e in ev if isinstance(e, Clarify))
    assert "E21" in c.question
    assert {o.manual_id for o in c.options} == {"washer_a", "oven_b"}
    assert all(o.message == "What does this code mean?" for o in c.options)


def test_auto_manual_photo_code_in_no_manual_says_so(ctx_full, fake_brain, tmp_path, monkeypatch):
    shelf(tmp_path, monkeypatch, {"washer_a": ["E21 means the washer cannot drain."],
                                  "oven_b": ["F3 means the oven sensor failed."]})
    fake_brain("E99", "E99")
    ev = list(homefix.run(img_req(tmp_path, "What does this code mean?", "manual_lookup", "auto"), ctx_full))
    r = next(e for e in ev if isinstance(e, Refusal))
    assert r.reason == "not_in_document" and "E99" in r.message


def test_resolve_manual_photo_waits_for_the_code_when_the_question_names_no_appliance(tmp_path, monkeypatch):
    shelf(tmp_path, monkeypatch, {"washer_a": ["x"], "oven_b": ["y"]})
    att = [Attachment(tmp_path / "a.jpg", "image", "a.jpg")]
    assert orchestrate.resolve_manual("auto", "What does this mean?", att) == orchestrate.AUTO_MANUAL
    assert orchestrate.resolve_manual("auto", "My washer shows this. What does it mean?", att) == "washer_a"


def test_resolve_manual_text_question_uses_the_manual_that_mentions_it(tmp_path, monkeypatch):
    shelf(tmp_path, monkeypatch, {"guide_a": ["If a breaker trips, unplug what you were using."],
                                  "guide_b": ["Clean the filter once a month."]})
    assert orchestrate.resolve_manual("auto", "What should I do if a breaker trips?", []) == "guide_a"


def test_handle_asks_which_manual_when_the_question_could_be_either(ctx_lite, tmp_path, monkeypatch):
    shelf(tmp_path, monkeypatch, {"washer_a": ["Clean the filter once a month."],
                                  "dishwasher_b": ["Clean the filter every week."]})
    monkeypatch.setattr("app.pipelines.text.run", lambda req, ctx: pytest.fail("must ask first"))
    ev = list(orchestrate.handle("How often should I clean the filter?", [], "auto", ctx_lite))
    c = next(e for e in ev if isinstance(e, Clarify))
    assert {o.manual_id for o in c.options} == {"washer_a", "dishwasher_b"}
    assert isinstance(ev[-1], Final) and ev[-1].answer == c.question


# ---- a photo with a problem question but no code: the manual answers, with a quote ----

def test_no_code_but_a_manual_that_answers_the_question_quotes_it(ctx_full, fake_brain, tmp_path, monkeypatch):
    shelf(tmp_path, monkeypatch, {"alarm": ["One short chirp every 30 to 60 seconds: the battery is low. Tell maintenance."]})
    fake_brain("CO SMOKE TEST", "CO SMOKE TEST",
               '{"answer":"The battery is low. Tell maintenance.",'
               '"quote":"One short chirp every 30 to 60 seconds: the battery is low.","page":1}')
    ev = list(homefix.run(img_req(tmp_path, "My smoke alarm keeps chirping. What should I do?", "manual_lookup", "alarm"),
                          ctx_full))
    assert next(e for e in ev if isinstance(e, Citation)).page == 1
    assert ev[-1].modality == "homefix" and ev[-1].answer == "The battery is low. Tell maintenance."
    assert "chirping" in fake_brain.calls[-1]["messages"][-1]["content"]  # the person's question, not "error code"


def test_no_code_and_the_manual_doesnt_say_falls_back_to_the_photo(ctx_full, fake_brain, tmp_path, monkeypatch):
    shelf(tmp_path, monkeypatch, {"alarm": ["Test the alarm monthly with the test button."]})
    fake_brain("I can't tell.", "I can't tell.", '{"answer":null,"quote":null,"page":null}',
               "Water is dripping from a joint in the pipe.")
    ev = list(homefix.run(img_req(tmp_path, "This pipe is leaking. What should I do?", "manual_lookup", "alarm"),
                          ctx_full))
    assert not any(isinstance(e, Citation) for e in ev)
    assert ev[-1].answer == "Water is dripping from a joint in the pipe."


def test_no_code_with_auto_uses_the_one_manual_that_fits(ctx_full, fake_brain, tmp_path, monkeypatch):
    shelf(tmp_path, monkeypatch, {"alarm_guide": ["One short chirp every 30 to 60 seconds: the battery is low."],
                                  "dishwasher_guide": ["E24 means the dishwasher cannot drain."]})
    fake_brain("SMOKE", "SMOKE", '{"answer":"The battery is low.",'
               '"quote":"One short chirp every 30 to 60 seconds: the battery is low.","page":1}')
    ev = list(homefix.run(img_req(tmp_path, "My alarm keeps chirping every minute. Help me fix it.", "manual_lookup",
                                  "auto"), ctx_full))
    assert next(e for e in ev if isinstance(e, Citation)).source == "alarm_guide.pdf"
    assert any(isinstance(e, Status) and (e.detail or "").startswith("Using the manual") for e in ev)
