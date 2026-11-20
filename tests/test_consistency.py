"""Self-consistency: a display is read twice (two wordings). If the numbers on it differ between the two reads,
HomeFix doesn't pick one: it shows both and asks which is right. A reading the person gives is used as is."""

import pymupdf

from app import clarify
from app.contracts import Attachment, Citation, Clarify, PipelineRequest, Status
from app.pipelines import homefix, image, text
from app.prompts import READ_PROMPT, READ_PROMPT_2
from tests.media_fixtures import make_jpeg


def req(tmp_path, message, qtype="qa", manual_id=None):
    att = Attachment(make_jpeg(tmp_path / "p.jpg", circles=1), "image", "p.jpg")
    return PipelineRequest(message, [att], qtype, manual_id)


def test_numbers_compare_the_digits_only():
    assert clarify.numbers("80 COOL F") == clarify.numbers("TEMP\n80\nCOOL") == {"80"}
    assert clarify.numbers("68°F SET") == clarify.numbers("68 °F") == {"68"}
    assert clarify.numbers("8:32 COOKTOP ON") == {"8:32"}
    assert clarify.numbers("E24 h min") != clarify.numbers("624 h min")


def test_extra_small_print_in_one_read_is_not_a_conflict():
    """The second wording lists everything, so it often adds a model number. Only a number each read lacks counts."""
    assert clarify.reads_agree("80 COOL", "TEMP 80 COOL Hunter 44110")
    assert clarify.reads_agree("TEMP 80 COOL Hunter 44110", "80 COOL")
    assert not clarify.reads_agree("80 COOL", "60 COOL")
    assert not clarify.reads_agree("E24 h min", "624 h min")


def test_two_reads_that_agree_answer_as_before(ctx_full, fake_brain, tmp_path):
    fake_brain("80 COOL", "TEMP\n80\nCOOL", "The thermostat is set to 80 and cooling.")
    ev = list(image.run(req(tmp_path, "What temperature is it set to?"), ctx_full))
    assert ev[-1].answer == "The thermostat is set to 80 and cooling."
    prompts = [c["messages"][-1]["content"] for c in fake_brain.calls]
    assert prompts[0] == READ_PROMPT and prompts[1] == READ_PROMPT_2


def test_two_reads_that_disagree_get_a_third_and_the_majority_answers(ctx_full, fake_brain, tmp_path):
    """E24 asked back about half the time with two reads; a third read settles most of those."""
    fake_brain("80 COOL", "60 COOL", "80\nCOOL", "The thermostat is set to 80 and cooling.")
    ev = list(image.run(req(tmp_path, "What temperature is it set to?"), ctx_full))
    assert not any(isinstance(e, Clarify) for e in ev)
    assert ev[-1].answer == "The thermostat is set to 80 and cooling."
    assert "80 COOL" in fake_brain.calls[3]["messages"][-1]["content"]  # answered from the majority reading


def test_three_reads_that_all_disagree_ask_which_is_right(ctx_full, fake_brain, tmp_path):
    fake_brain("80 COOL", "60 COOL", "88 COOL")
    ev = list(image.run(req(tmp_path, "What temperature is it set to?"), ctx_full))
    c = next(e for e in ev if isinstance(e, Clarify))
    assert "two different ways" in c.question
    assert "80 COOL" in c.seen and "60 COOL" in c.seen
    assert [o.label for o in c.options] == ["It shows 80", "It shows 60"]
    assert c.options[0].message == "What temperature is it set to?\nThe display shows: 80 COOL"
    assert len(fake_brain.calls) == 3  # no answer from a reading it isn't sure of


def test_a_reading_you_give_is_used_without_reading_the_photo(ctx_full, fake_brain, tmp_path):
    fake_brain("The thermostat is set to 80.")
    ev = list(image.run(req(tmp_path, "What temperature is it set to?\nThe display shows: 80 COOL"), ctx_full))
    assert ev[-1].answer == "The thermostat is set to 80."
    assert len(fake_brain.calls) == 1
    assert "80 COOL" in fake_brain.calls[0]["messages"][-1]["content"]
    assert fake_brain.calls[0]["images"] is None


def test_no_second_read_when_the_first_isnt_a_display(ctx_full, fake_brain, tmp_path):
    fake_brain("I can't tell.", "The mug is blue.")
    list(image.run(req(tmp_path, "What color is the mug?"), ctx_full))
    assert len(fake_brain.calls) == 2


def shelf(tmp_path, monkeypatch, pages):
    monkeypatch.setattr(text, "MANUALS_DIR", tmp_path)
    d = pymupdf.open()
    for t in pages:
        d.new_page().insert_text((72, 72), t)
    d.save(tmp_path / "w1.pdf")


def test_two_reads_that_find_different_codes_get_a_third_and_the_majority_code_is_used(ctx_full, fake_brain, tmp_path,
                                                                                     monkeypatch):
    shelf(tmp_path, monkeypatch, ["E24 means the dishwasher cannot drain."])
    fake_brain("E24 h min", "624 h min", "E24", '{"answer":"It cannot drain.","quote":"E24 means the dishwasher cannot drain","page":1}')
    ev = list(homefix.run(req(tmp_path, "My dishwasher shows this code. Help me fix it.", "manual_lookup", "w1"),
                          ctx_full))
    assert not any(isinstance(e, Clarify) for e in ev)
    assert any(isinstance(e, Status) and e.detail == "found E24" for e in ev)


def test_three_reads_with_no_majority_code_ask_which_code(ctx_full, fake_brain, tmp_path, monkeypatch):
    shelf(tmp_path, monkeypatch, ["E24 means the dishwasher cannot drain."])
    fake_brain("E24 h min", "624 h min", "E25")
    ev = list(homefix.run(req(tmp_path, "My dishwasher shows this code. Help me fix it.", "manual_lookup", "w1"),
                          ctx_full))
    c = next(e for e in ev if isinstance(e, Clarify))
    assert "two different ways" in c.question
    assert [o.label for o in c.options] == ["It shows E24", "It shows E25"]
    assert c.options[0].message.endswith("It shows E24")


def test_two_reads_with_the_same_code_go_to_the_manual(ctx_full, fake_brain, tmp_path, monkeypatch):
    shelf(tmp_path, monkeypatch, ["E24 means the dishwasher cannot drain."])
    fake_brain("E24", "E24 h min", '{"answer":"It cannot drain.","quote":"E24 means the dishwasher cannot drain","page":1}')
    ev = list(homefix.run(req(tmp_path, "My dishwasher shows this code. Help me fix it.", "manual_lookup", "w1"),
                          ctx_full))
    assert any(isinstance(e, Citation) for e in ev)


def test_a_code_you_typed_wins_and_the_photo_isnt_read(ctx_full, fake_brain, tmp_path, monkeypatch):
    shelf(tmp_path, monkeypatch, ["E24 means the dishwasher cannot drain."])
    fake_brain('{"answer":"It cannot drain.","quote":"E24 means the dishwasher cannot drain","page":1}')
    ev = list(homefix.run(req(tmp_path, "My dishwasher shows this code. Help me fix it.\nIt shows E24",
                              "manual_lookup", "w1"), ctx_full))
    assert any(isinstance(e, Status) and e.detail == "found E24" for e in ev)
    assert len(fake_brain.calls) == 1
