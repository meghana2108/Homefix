"""Intent by meaning: "is this a problem?" and "is this vague?" are the word rule OR the meaning, never less."""

from pathlib import Path

import pytest
import yaml

from app import intent, orchestrate
from app.contracts import Final

DATA = Path(__file__).parent / "data"


def leaning(monkeypatch, value):
    monkeypatch.setattr(intent, "lean", lambda text, side, other: value)


def test_problem_words_need_no_model(monkeypatch):
    monkeypatch.setattr(intent, "lean", lambda *a: pytest.fail("the word rule already decided"))
    assert intent.is_problem("my dishwasher won't drain")
    assert intent.intent_of("there's mold on the ceiling") == "problem"


def test_meaning_can_add_a_problem_the_words_miss(monkeypatch):
    leaning(monkeypatch, 0.20)
    assert intent.is_problem("the fridge sounds weird")
    leaning(monkeypatch, -0.20)
    assert not intent.is_problem("is it heating or cooling?")
    assert intent.intent_of("is it heating or cooling?") == "question"


def test_meaning_can_add_vague_but_never_remove_it(monkeypatch):
    leaning(monkeypatch, 0.30)
    assert intent.is_vague("what's this thingy?")
    leaning(monkeypatch, -0.90)
    assert intent.is_vague("What is this?")  # the word rule says vague; meaning can't undo it


def test_no_model_means_the_word_rules_decide(monkeypatch):
    def boom(*a):
        raise OSError("not cached")
    monkeypatch.setattr(intent, "lean", boom)
    assert intent.is_problem("the sink is clogged") and not intent.is_problem("the fridge sounds weird")


def test_the_final_answer_says_whether_it_was_a_problem(ctx_lite, monkeypatch):
    monkeypatch.setattr("app.pipelines.code.run", lambda req, ctx: iter(()))
    ev = list(orchestrate.handle("my washer won't drain", [], None, ctx_lite))
    assert isinstance(ev[-1], Final) and ev[-1].intent == "problem"
    ev = list(orchestrate.handle("Can I have a cat?", [], None, ctx_lite))
    assert ev[-1].intent == "question"


@pytest.mark.model
def test_held_out_intent_with_the_real_model():
    """Measured 2026-11-20 on tests/data/intent_test.yaml (never tuned on): problem words alone 4/10, with
    meaning 10/10 (1/10 questions wrongly called a problem); vague words alone 2/6, with meaning 6/6 (0/6 wrong)."""
    d = yaml.safe_load((DATA / "intent_test.yaml").read_text())
    assert sum(intent.is_problem(q) for q in d["problem"]) >= 10
    assert sum(intent.is_problem(q) for q in d["question"]) <= 1
    assert sum(intent.is_vague(q) for q in d["vague"]) >= 6
    assert sum(intent.is_vague(q) for q in d["specific"]) == 0
