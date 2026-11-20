"""A sound that could be an alarm or something harmless (a real kettle was labelled "carbon monoxide alarm 18%"):
HomeFix asks what's on instead of picking, and never drops the "treat it as an alarm" advice."""

import pytest

from app.contracts import Attachment, Clarify, Final, PipelineRequest, Refusal, SoundLabel
from app.pipelines import audio


def run(ctx, tmp_path, monkeypatch, labels, message="What is this sound?"):
    monkeypatch.setattr(audio, "classify", lambda path, repo, vocab, top_k: [SoundLabel(label=a, score=b) for a, b in labels])
    att = Attachment(tmp_path / "s.wav", "audio", "s.wav")
    return list(audio.run(PipelineRequest(message, [att], "sound"), ctx))


KETTLE = [("carbon monoxide alarm", 0.18), ("buzz", 0.07), ("smoke detector, smoke alarm", 0.06)]
KETTLE_TOO = [("kettle whistling", 0.15), ("carbon monoxide alarm", 0.12), ("whistle", 0.08)]


def test_a_possible_alarm_asks_what_is_on_and_keeps_the_warning(ctx_lite, tmp_path, monkeypatch):
    ev = run(ctx_lite, tmp_path, monkeypatch, KETTLE)
    c = next(e for e in ev if isinstance(e, Clarify))
    assert "carbon monoxide alarm" in c.question
    assert "If you're not sure, treat it as an alarm: leave and call 911 from outside." in c.question
    assert [o.label for o in c.options] == ["Yes, a kettle, timer or appliance is on", "No, nothing like that"]
    assert not any(isinstance(e, Refusal) for e in ev)
    assert isinstance(ev[-1], Final) and ev[-1].answer.startswith("This could be")


def test_the_harmless_look_alike_it_heard_is_named(ctx_lite, tmp_path, monkeypatch):
    c = next(e for e in run(ctx_lite, tmp_path, monkeypatch, KETTLE_TOO) if isinstance(e, Clarify))
    assert "kettle whistling" in c.question
    assert c.options[0].label == "Yes, kettle whistling"


def test_a_confident_alarm_still_stops_at_once(ctx_lite, tmp_path, monkeypatch):
    ev = run(ctx_lite, tmp_path, monkeypatch, [("smoke alarm beeping loudly", 0.62), ("beep, bleep", 0.1)])
    assert next(e for e in ev if isinstance(e, Refusal)).reason == "safety"
    assert not any(isinstance(e, Clarify) for e in ev)


@pytest.mark.parametrize("reply", ["It's not an alarm: something like a kettle or a timer is on.", "it's the kettle",
                                   "yes the microwave just finished"])
def test_something_harmless_is_on_answer_with_the_warning_kept(ctx_lite, tmp_path, monkeypatch, reply):
    ev = run(ctx_lite, tmp_path, monkeypatch, KETTLE, f"What is this sound?\n{reply}")
    assert not any(isinstance(e, Clarify | Refusal) for e in ev)
    a = ev[-1].answer
    assert a.startswith("Then it's most likely")
    assert "If it keeps going after that's turned off, or you're not sure, treat it as an alarm" in a


@pytest.mark.parametrize("reply", ["Nothing like that is on.", "no", "not sure", "I don't know"])
def test_nothing_is_on_or_unsure_stops(ctx_lite, tmp_path, monkeypatch, reply):
    ev = run(ctx_lite, tmp_path, monkeypatch, KETTLE, f"What is this sound?\n{reply}")
    r = next(e for e in ev if isinstance(e, Refusal))
    assert r.reason == "safety" and r.category == "gas"  # a CO alarm


def test_the_question_itself_naming_a_kettle_doesnt_skip_asking(ctx_lite, tmp_path, monkeypatch):
    """Only a reply (after the first line) can say what's on; "Is this my kettle or the alarm?" still asks."""
    ev = run(ctx_lite, tmp_path, monkeypatch, KETTLE, "Is this my kettle or the CO alarm?")
    assert any(isinstance(e, Clarify) for e in ev)


def test_ordinary_beeps_are_unchanged(ctx_lite, tmp_path, monkeypatch):
    ev = run(ctx_lite, tmp_path, monkeypatch, [("microwave beeping", 0.19), ("washing machine beeping", 0.18),
                                               ("busy signal", 0.11)])
    assert not any(isinstance(e, Clarify | Refusal) for e in ev)
    assert ev[-1].answer.startswith("Most likely")
