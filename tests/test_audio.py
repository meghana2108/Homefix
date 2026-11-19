"""Audio pipeline: voice notes get a transcript (+ answer); sounds get top-3 labels; danger gets
the safety message before any model answer."""

from pathlib import Path

import pytest

from app.contracts import (
    MESSAGES,
    Attachment,
    Final,
    ModelUnavailable,
    PipelineRequest,
    Refusal,
    SoundLabel,
    SoundLabels,
    Status,
    Token,
    Transcript,
)
from app.models.whisper import TranscriptResult
from app.pipelines import audio
from app.safety import SAFETY_MESSAGE

WAV = Attachment(path=Path("/tmp/note.wav"), kind="audio", original_name="note.m4a")
BEEPS = [SoundLabel(label="washing machine beeping", score=0.71), SoundLabel(label="beep", score=0.12),
         SoundLabel(label="alarm", score=0.05)]


@pytest.fixture
def heard(monkeypatch):
    """heard(text, no_speech=0.1, labels=BEEPS): what Whisper and CLAP will return."""
    calls = {"transcribe": 0, "classify": 0}

    def set_(text, no_speech=0.1, labels=BEEPS, seconds=4.2):
        def fake_transcribe(path, repo):
            calls["transcribe"] += 1
            calls["whisper_repo"] = repo
            return TranscriptResult(text=text, seconds=seconds, mean_no_speech_prob=no_speech)

        def fake_classify(path, repo, labels_, top_k=3):
            calls["classify"] += 1
            calls["clap_repo"], calls["n_labels"], calls["top_k"] = repo, len(labels_), top_k
            return labels[:top_k]
        monkeypatch.setattr(audio, "transcribe", fake_transcribe)
        monkeypatch.setattr(audio, "classify", fake_classify)
        return calls
    return set_


def run(ctx, message="", qtype="none", attachments=(WAV,)):
    return list(audio.run(PipelineRequest(message, list(attachments), qtype), ctx))


def of(events, cls):
    return [e for e in events if isinstance(e, cls)]


def test_speech_with_question(ctx_lite, heard, fake_brain):
    heard("The washer shows E21 and won't drain.")
    fake_brain("It shows E21.")
    ev = run(ctx_lite, "What did she say the washer shows?", "speech")
    assert ev[0] == Status(stage="transcribing")
    tr = of(ev, Transcript)
    assert tr == [Transcript(text="The washer shows E21 and won't drain.", seconds=4.2)]
    assert ev.index(tr[0]) < ev.index(of(ev, Token)[0])
    assert ev[-1].answer == "It shows E21." and ev[-1].modality == "audio" and ev[-1].question_type == "speech"
    assert ev[-1].model == ctx_lite.profile.models.brain
    prompt = fake_brain.calls[0]["messages"][-1]["content"]
    assert "The washer shows E21 and won't drain." in prompt and "What did she say" in prompt
    assert fake_brain.calls[0]["images"] is None


def test_speech_without_question_is_transcript(ctx_lite, heard, fake_brain):
    calls = heard("Remind me to call the landlord about the dishwasher.")
    fake_brain()
    ev = run(ctx_lite, "", "none")
    assert ev[-1].answer == "Remind me to call the landlord about the dishwasher."
    assert ev[-1].question_type == "speech"
    assert ev[-1].model == ctx_lite.profile.models.whisper_file == calls["whisper_repo"]
    assert fake_brain.calls == [] and calls["classify"] == 0


def test_router_sound_forces_sound_path(ctx_lite, heard, fake_brain):
    calls = heard("This sounds like a normal spoken sentence to me.")
    fake_brain()
    ev = run(ctx_lite, "What is this beeping sound?", "sound")
    assert of(ev, Transcript) == []
    assert of(ev, SoundLabels) == [SoundLabels(labels=BEEPS, is_speech=False)]
    assert calls["classify"] == 1 and calls["top_k"] == 3 and calls["n_labels"] >= 400
    assert ev[-1].answer == "Sounds like: washing machine beeping (71%), beep, alarm."
    assert ev[-1].model == ctx_lite.profile.models.clap and ev[-1].question_type == "sound"


def test_spoken_gas_is_safety_before_brain(ctx_lite, heard, fake_brain):
    heard("I smell gas in the kitchen")
    fake_brain()
    ev = run(ctx_lite, "what should I do?", "speech")
    assert of(ev, Transcript)
    assert ev[-2] == Refusal(reason="safety", message=SAFETY_MESSAGE, category="gas")
    assert isinstance(ev[-1], Final) and ev[-1].answer == ""
    assert fake_brain.calls == [] and of(ev, Token) == []


def test_loud_smoke_alarm_labels_then_safety(ctx_lite, heard, fake_brain):
    heard("", no_speech=0.9, labels=[SoundLabel(label="smoke alarm beeping loudly", score=0.71), *BEEPS[1:]])
    ev = run(ctx_lite, "", "none")
    assert of(ev, SoundLabels)[0].labels[0].label == "smoke alarm beeping loudly"
    assert ev[-2].type == "refusal" and ev[-2].reason == "safety" and ev[-2].category == "smoke_fire"
    assert ev[-1].answer == ""


def test_quiet_smoke_alarm_is_just_labels(ctx_lite, heard):
    heard("", no_speech=0.9, labels=[SoundLabel(label="smoke alarm beeping loudly", score=0.32), *BEEPS[1:]])
    ev = run(ctx_lite, "", "none")
    assert of(ev, Refusal) == []
    assert ev[-1].answer == "Sounds like: smoke alarm beeping loudly (32%), beep, alarm."


def test_two_words_is_sound(ctx_lite, heard):
    heard("Thank you.", no_speech=0.2)  # Whisper often 'hears' this in a beep
    ev = run(ctx_lite, "", "none")
    assert of(ev, SoundLabels) and of(ev, Transcript) == []
    assert ev[-1].question_type == "sound"


def test_high_no_speech_prob_is_sound(ctx_lite, heard):
    heard("the the the the the", no_speech=0.8)
    assert of(run(ctx_lite, "", "none"), SoundLabels)


def test_router_speech_but_silent_falls_back_to_sound(ctx_lite, heard):
    heard("", no_speech=1.0)
    ev = run(ctx_lite, "What did he say?", "speech")
    assert of(ev, SoundLabels) and of(ev, Transcript) == []


def test_whisper_missing_refuses(ctx_lite, monkeypatch):
    def boom(path, repo):
        raise ModelUnavailable(MESSAGES["model_missing"].format(role="whisper"))
    monkeypatch.setattr(audio, "transcribe", boom)
    ev = run(ctx_lite, "", "speech")
    assert ev[-2] == Refusal(reason="model_unavailable",
                             message="The whisper model isn't installed. Run scripts/pull_models.sh.")
    assert isinstance(ev[-1], Final)


def test_clap_missing_refuses(ctx_lite, heard, monkeypatch):
    heard("", no_speech=1.0)

    def boom(*a, **kw):
        raise ModelUnavailable(MESSAGES["model_missing"].format(role="sound"))
    monkeypatch.setattr(audio, "classify", boom)
    ev = run(ctx_lite, "", "sound")
    assert ev[-2].reason == "model_unavailable" and isinstance(ev[-1], Final)


def test_brain_down_after_transcript(ctx_lite, heard, monkeypatch):
    """Transcript still shows; the answer step refuses; exactly one final."""
    from app.models import ollama_client

    heard("The washer shows E21.")

    def down(*a, **kw):
        raise ModelUnavailable(MESSAGES["ollama_down"])
        yield  # pragma: no cover
    monkeypatch.setattr(ollama_client, "chat_stream", down)
    ev = run(ctx_lite, "what does it show?", "speech")
    assert of(ev, Transcript) and ev[-2].reason == "model_unavailable"
    assert len(of(ev, Final)) == 1 and ev[-1].answer == ""


def test_no_audio_attachment(ctx_lite):
    ev = run(ctx_lite, "hi", "speech", attachments=())
    assert ev[-2].type == "refusal" and isinstance(ev[-1], Final)


def test_is_speech_rules():
    tr = TranscriptResult
    assert audio.is_speech("speech", tr("hi there you", 1, 0.1), 0.6)
    assert not audio.is_speech("sound", tr("one two three four", 1, 0.0), 0.6)
    assert audio.is_speech("none", tr("one two three", 1, 0.59), 0.6)
    assert not audio.is_speech("none", tr("one two three", 1, 0.6), 0.6)
    assert not audio.is_speech("none", tr("one two", 1, 0.0), 0.6)
    assert not audio.is_speech("speech", tr("", 1, 1.0), 0.6)


@pytest.mark.model
def test_real_beep_on_lite(ctx_lite, tmp_path):
    from tests import media_fixtures as mf

    wav = mf.make_sine_wav(tmp_path / "beep.wav", hz=2800, sr=16000)
    ev = run(ctx_lite, "what is this sound?", "sound", [Attachment(wav, "audio", "beep.wav")])
    labels = of(ev, SoundLabels)[0].labels
    assert len(labels) == 3 and ev[-1].answer.startswith("Sounds like: ")


@pytest.mark.model
def test_real_voice_note_on_lite(tmp_path, profile_lite):
    """Real Whisper + real brain on the M2."""
    from app.contracts import Ctx
    from app.models.memory import MemoryManager
    from app.models.ollama_client import OllamaBackend
    from tests import media_fixtures as mf

    ctx = Ctx(profile_lite, MemoryManager(profile_lite, OllamaBackend()), deadline_s=90)
    wav = mf.make_speech_wav(tmp_path / "v.wav", "The washing machine shows error E twenty one.")
    ev = run(ctx, "What error does the washer show?", "speech", [Attachment(wav, "audio", "v.wav")])
    assert "washing" in of(ev, Transcript)[0].text.lower()
    assert "21" in ev[-1].answer or "twenty" in ev[-1].answer.lower()
