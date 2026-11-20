"""Danger seen in a photo stops like danger in your words. Two parts:
- a focused look ("any burn marks, melting, smoke, sparks, exposed wires, water near electrics?"), twice, before a
  vague or safety question ("What is this?", "Is this okay to use?"); either look naming a sign stops;
- every description, reading or answer the model gives about a photo is scanned for observed danger words.
Neither can clear a stop; a plain specific question ("What temperature?") gets no extra look."""

import pytest

from app import safety
from app.contracts import Attachment, Final, PipelineRequest, Refusal, Status, Token
from app.pipelines import homefix, image
from tests.media_fixtures import make_jpeg


def req(tmp_path, message, qtype="qa", manual_id=None):
    att = Attachment(make_jpeg(tmp_path / "p.jpg", circles=1), "image", "p.jpg")
    return PipelineRequest(message, [att], qtype, manual_id)


def stopped(events):
    r = next((e for e in events if isinstance(e, Refusal)), None)
    return r if r is not None and r.reason == "safety" else None


@pytest.mark.parametrize(("seen", "category"), [
    ("exposed or frayed wires", "exposed_wires"),
    ("There are burn marks and melted plastic around the plug.", "smoke_fire"),
    ("Water is dripping onto the outlet.", "water_electric"),
    ("sparks", "sparks"),
])
def test_a_vague_question_gets_a_danger_look_first(ctx_full, fake_brain, tmp_path, seen, category):
    fake_brain(seen)
    ev = list(image.run(req(tmp_path, "What is this?", "describe"), ctx_full))
    r = stopped(ev)
    assert r and r.category == category
    assert len(fake_brain.calls) == 1  # stopped at the first look: no reading, no answer
    assert "signs of danger" in fake_brain.calls[0]["messages"][-1]["content"]
    assert any(isinstance(e, Status) and e.stage == "safety_check" and "photo" in (e.detail or "") for e in ev)
    assert isinstance(ev[-1], Final) and ev[-1].answer == ""


def test_a_safety_question_looks_twice_and_either_look_can_stop(ctx_full, fake_brain, tmp_path):
    fake_brain("None", "exposed or frayed wires")
    ev = list(image.run(req(tmp_path, "Is this okay to use?"), ctx_full))
    assert stopped(ev).category == "exposed_wires"
    assert len(fake_brain.calls) == 2


def test_two_clean_looks_then_the_normal_answer(ctx_full, fake_brain, tmp_path):
    fake_brain("None", "None.", "I can't tell.", "A glowing electric heating element on a stovetop.")
    ev = list(image.run(req(tmp_path, "What is this?", "describe"), ctx_full))
    assert stopped(ev) is None
    assert ev[-1].answer == "A glowing electric heating element on a stovetop."


def test_a_model_that_repeats_the_whole_list_counts_as_danger(ctx_full, fake_brain, tmp_path):
    """Seen on the M2: the first look echoed every sign. Unsure means stop."""
    fake_brain("burn or scorch marks, melted plastic, smoke, sparks, exposed or frayed wires, water on or near "
               "electrical parts")
    assert stopped(list(image.run(req(tmp_path, "Is this safe?"), ctx_full)))


@pytest.mark.parametrize("text", ["There are no signs of danger such as burn marks or sparks.", "None", "none.",
                                  "No signs of danger.", "I see none of them."])
def test_none_means_none(text):
    assert image.danger_named(text) is None


def test_a_plain_specific_question_gets_no_extra_look(ctx_full, fake_brain, tmp_path):
    fake_brain("I can't tell.", "The mug is blue.")
    ev = list(image.run(req(tmp_path, "What color is the mug?"), ctx_full))
    assert ev[-1].answer == "The mug is blue."
    assert not any("signs of danger" in c["messages"][-1]["content"] for c in fake_brain.calls)


def test_a_description_that_mentions_danger_stops_after_it(ctx_full, fake_brain, tmp_path):
    fake_brain("A close-up of a metal ferrule with a dark burnt tip and charred edges.")
    ev = list(image.run(req(tmp_path, "Describe the photo.", "describe"), ctx_full))
    r = stopped(ev)
    assert r and r.category == "smoke_fire"
    assert ev[-1].answer == ""  # the streamed description isn't kept as an answer
    assert any(isinstance(e, Token) for e in ev)


@pytest.mark.parametrize("text", [
    "A close-up of a glowing red electric heating element on a stovetop.",
    "A gas burner with blue flames under a pot.",
    "A gray electrical panel with breakers numbered 1 to 13.",
    "The thermostat shows 80 and COOL.",
    "A dark stain on the ceiling tile.",
])
def test_ordinary_descriptions_dont_stop(text):
    assert safety.check_observation(text) is None


@pytest.mark.parametrize(("text", "category"), [
    ("The outlet has burn marks around the left socket.", "smoke_fire"),
    ("The plug's plastic is melted.", "smoke_fire"),
    ("Exposed wiring is visible behind the switch.", "exposed_wires"),
    ("The cord is frayed and the copper wire shows.", "exposed_wires"),
    ("Smoke is coming out of the toaster.", "smoke_fire"),
    ("Water is pooling under the breaker panel.", "water_electric"),
    ("Sparks fly from the socket.", "sparks"),
])
def test_observed_danger_words(text, category):
    hit = safety.check_observation(text)
    assert hit and hit.category == category


def test_the_manual_path_looks_too_when_asked_whats_wrong(ctx_full, fake_brain, tmp_path, monkeypatch):
    fake_brain("burn or scorch marks")
    ev = list(homefix.run(req(tmp_path, "What's wrong with it?", "manual_lookup", "w1"), ctx_full))
    assert stopped(ev).category == "smoke_fire"
