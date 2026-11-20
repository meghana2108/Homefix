"""The meaning-based danger net: catches paraphrases the regex misses, and only ever ADDS a stop."""

from pathlib import Path

import pytest
import yaml

from app import orchestrate, safety_semantic
from app.contracts import Refusal
from app.safety import check
from app.safety_semantic import check_all, check_meaning

DATA = Path(__file__).parent / "data"


def fixed(haz, safe, cat="gas"):
    return lambda text: (haz, safe, cat)


def test_close_to_a_hazard_and_far_from_safe_stops(monkeypatch):
    monkeypatch.setattr(safety_semantic, "scores", fixed(0.90, 0.60))
    hit = check_meaning("there's a weird sulfur smell by the oven")
    assert hit and hit.category == "gas"


@pytest.mark.parametrize(("haz", "safe"), [(0.90, 0.88), (0.65, 0.40)])
def test_too_close_to_safe_or_not_close_enough_to_a_hazard_passes(monkeypatch, haz, safe):
    monkeypatch.setattr(safety_semantic, "scores", fixed(haz, safe))
    assert check_meaning("the stove takes a while to heat up") is None


def test_empty_text_never_stops(monkeypatch):
    monkeypatch.setattr(safety_semantic, "scores", lambda t: pytest.fail("no need to embed nothing"))
    assert check_meaning("   ") is None


def test_a_model_that_wont_load_leaves_the_regex_in_charge(monkeypatch):
    def boom(text):
        raise OSError("model not cached")
    monkeypatch.setattr(safety_semantic, "scores", boom)
    assert check_meaning("there's a weird sulfur smell by the oven") is None
    assert check_all("I smell gas").category == "gas"  # the regex still stops


def test_the_regex_decides_first_and_the_net_can_only_add(monkeypatch):
    monkeypatch.setattr(safety_semantic, "scores", lambda t: pytest.fail("regex already stopped it"))
    assert check_all("Sparks came out of the outlet").category == "sparks"
    monkeypatch.setattr(safety_semantic, "scores", fixed(0.10, 0.90))  # "very safe" can't clear a regex stop
    assert check_all("I smell gas in the kitchen") is not None


def test_handle_stops_a_paraphrase_before_any_model(ctx_lite, monkeypatch):
    monkeypatch.setattr(safety_semantic, "scores", fixed(0.92, 0.60, "gas"))
    monkeypatch.setattr("app.pipelines.text.run", lambda req, ctx: pytest.fail("no model after a danger stop"))
    events = list(orchestrate.handle("there's a weird sulfur smell by the oven", [], None, ctx_lite))
    r = next(e for e in events if isinstance(e, Refusal))
    assert r.reason == "safety" and r.category == "gas"


def test_a_spoken_paraphrase_stops_too(ctx_lite, monkeypatch, tmp_path):
    from app.contracts import Attachment, PipelineRequest
    from app.models.whisper import TranscriptResult
    from app.pipelines import audio
    monkeypatch.setattr(safety_semantic, "scores", fixed(0.92, 0.60, "sparks"))
    monkeypatch.setattr(audio, "transcribe", lambda p, r: TranscriptResult(
        text="Hi, the wall socket in the kitchen is crackling and it feels warm.", seconds=4.0, mean_no_speech_prob=0.0))
    att = Attachment(tmp_path / "v.wav", "audio", "v.wav")
    events = list(audio.run(PipelineRequest("What should I do?", [att], "speech"), ctx_lite))
    assert any(isinstance(e, Refusal) and e.reason == "safety" for e in events)


@pytest.mark.model
def test_held_out_set_with_the_real_embedding_model():
    """Report set, never used for tuning (tuned on tests/data/safety_dev.yaml). Measured 2026-11-20: regex alone
    12/25 caught; regex + meaning net 24/25 caught, 0/30 false stops."""
    d = yaml.safe_load((DATA / "safety_test.yaml").read_text())
    caught = sum(bool(check_all(q)) for q in d["danger"])
    false_stops = [q for q in d["ok"] if check_all(q)]
    assert caught >= 24 and false_stops == []
    assert sum(bool(check(q)) for q in d["danger"]) < caught  # the net adds real catches


@pytest.mark.model
def test_no_gallery_question_stops_except_the_danger_examples():
    import re
    src = (Path(__file__).parents[1] / "frontend/src/examples.ts").read_text()
    qs = re.findall(r'question: "((?:[^"\\]|\\.)*)"', src)
    assert [q for q in qs if check_all(q)] == ["I smell gas in the kitchen",
                                               "Sparks came out of the outlet when I plugged in the heater"]


@pytest.mark.model
def test_plain_plumbing_leaks_are_repairs_not_danger():
    """Found 2026-11-20 making problem->fix gallery examples: "This pipe is leaking" stopped like a hazard."""
    for q in ["This pipe is leaking. What should I do?", "Water keeps dripping from this pipe. Which way is it going?",
              "The pipe under the sink is leaking", "My faucet won't stop dripping"]:
        assert check_all(q) is None, q
