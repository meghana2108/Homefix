"""Whisper and CLAP loaders: load once, return plain results, clear message when a model is missing."""

import pytest

from app.contracts import ModelUnavailable, SoundLabel
from app.models import clap, whisper
from app.models.clap import classify, load_vocab
from app.models.whisper import TranscriptResult, transcribe
from app.settings import SOUND_LABEL_FILES
from tests import media_fixtures as mf


def test_vocab():
    vocab = load_vocab()
    assert len(vocab) >= 400
    assert "washing machine beeping" in vocab
    assert len(vocab) == len(set(vocab))
    assert not any(v.startswith("#") or not v.strip() for v in vocab)


def test_vocab_order_general_first():
    first_general = next(ln.strip() for ln in SOUND_LABEL_FILES[0].read_text().splitlines()
                         if ln.strip() and not ln.startswith("#"))
    assert load_vocab()[0] == first_general


def test_vocab_is_not_esc50():
    """Hard rule 3: hundreds of AudioSet-derived labels plus our appliances, never a 50-class lookup."""
    assert len(load_vocab()) > 50 * 5


def test_classify_top_k_sorted(monkeypatch, tmp_path):
    scores = [("rain", 0.05), ("beep, bleep", 0.6), ("dog", 0.01), ("alarm", 0.2), ("busy signal", 0.14)]
    monkeypatch.setattr(clap, "_score", lambda path, repo, labels: scores)
    out = classify(tmp_path / "x.wav", "repo", [s[0] for s in scores])
    assert out == [SoundLabel(label="beep, bleep", score=0.6), SoundLabel(label="alarm", score=0.2),
                   SoundLabel(label="busy signal", score=0.14)]


def test_classify_top_k_param(monkeypatch, tmp_path):
    monkeypatch.setattr(clap, "_score", lambda path, repo, labels: [("a", 0.5), ("b", 0.3), ("c", 0.2)])
    assert [s.label for s in classify(tmp_path / "x.wav", "repo", ["a", "b", "c"], top_k=2)] == ["a", "b"]


def test_clap_bad_repo_is_model_unavailable(tmp_path):
    with pytest.raises(ModelUnavailable) as e:
        classify(mf.make_sine_wav(tmp_path / "x.wav"), "nobody/not-a-clap-model", ["beep"])
    assert "Run scripts/pull_models.sh." in str(e.value)
    assert str(e.value).startswith("The sound model")


def test_whisper_bad_repo_is_model_unavailable(tmp_path):
    with pytest.raises(ModelUnavailable) as e:
        transcribe(mf.make_sine_wav(tmp_path / "x.wav"), "nobody/not-a-whisper-model")
    assert str(e.value) == "The whisper model isn't installed. Run scripts/pull_models.sh."


def test_whisper_result_shape(monkeypatch, tmp_path):
    monkeypatch.setattr(whisper, "_resolve", lambda repo: "/local/model")
    monkeypatch.setattr(whisper, "_run", lambda path, model: {
        "text": "  The washer shows E21. ",
        "segments": [{"no_speech_prob": 0.1}, {"no_speech_prob": 0.3}]})
    r = transcribe(mf.make_sine_wav(tmp_path / "x.wav", seconds=2.0), "repo")
    assert r.text == "The washer shows E21."
    assert r.seconds == pytest.approx(2.0, abs=0.01)
    assert r.mean_no_speech_prob == pytest.approx(0.2)


def test_whisper_no_segments_is_no_speech(monkeypatch, tmp_path):
    monkeypatch.setattr(whisper, "_resolve", lambda repo: "/local/model")
    monkeypatch.setattr(whisper, "_run", lambda path, model: {"text": "", "segments": []})
    r = transcribe(mf.make_sine_wav(tmp_path / "x.wav"), "repo")
    assert r == TranscriptResult(text="", seconds=pytest.approx(2.0, abs=0.01), mean_no_speech_prob=1.0)


@pytest.mark.model
def test_real_transcribe(tmp_path, profile_lite):
    wav = mf.make_speech_wav(tmp_path / "s.wav", "the washer shows error twenty one")
    r = transcribe(wav, profile_lite.models.whisper_file)
    assert "washer" in r.text.lower()
    assert r.mean_no_speech_prob < 0.6


@pytest.mark.model
def test_real_classify_beep(tmp_path, profile_lite):
    wav = mf.make_sine_wav(tmp_path / "b.wav", hz=2800)
    top = [s.label for s in classify(wav, profile_lite.models.clap, load_vocab())]
    assert len(top) == 3
    assert any(k in " ".join(top) for k in ("beep", "tone", "sine", "alarm", "buzzer"))


@pytest.mark.model
def test_real_classify_matches_hf_pipeline(tmp_path, profile_lite):
    """Our cached-text-embedding scorer gives the same scores as transformers' pipeline."""
    from transformers import pipeline

    wav = mf.make_sine_wav(tmp_path / "b.wav", hz=2800)
    labels = load_vocab()
    ref = pipeline("zero-shot-audio-classification", model=profile_lite.models.clap)(
        str(wav), candidate_labels=labels, hypothesis_template="This is a sound of {}.")
    ours = classify(wav, profile_lite.models.clap, labels, top_k=5)
    assert [s.label for s in ours] == [r["label"] for r in ref[:5]]
    assert all(abs(s.score - r["score"]) < 1e-4 for s, r in zip(ours, ref[:5], strict=True))
