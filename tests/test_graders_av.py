"""Audio and video graders (docs/EVAL.md). Every value here is invented, none from the pack."""

import pytest

from eval.graders import audio, video
from eval.types import PackItem, RunRecord


def item(modality, subtype="", question="q"):
    return PackItem(id="fake-1", modality=modality, question=question, path=None, meta={"subtype": subtype})


def ours(answer="", question_type="none", sound_labels=(), transcript=None, refusal=None, modality="audio"):
    return RunRecord(run_id="r", item_id="fake-1", modality=modality, question_type=question_type, answer=answer,
                     refusal_reason=refusal, code=None, sound_labels=list(sound_labels), latency_ms=1,
                     peak_mem_gb=1.0, profile="lite", model=None, transcript=transcript)


# ---------------------------------------------------------------- speech
def test_wer_identical_is_zero_and_hit():
    g = audio.grade(item("audio", "speech", ""), ours("The washer shows E21.", "speech",
                                                      transcript="The washer shows E21."),
                    {"transcript": "the washer shows e21"})
    assert (g.metric, g.score, g.hit) == ("wer", 0.0, True)


def test_wer_split_number_is_above_zero():
    g = audio.grade(item("audio", "speech", ""), ours(transcript="the washer shows e21"),
                    {"transcript": "the washer shows e 21"})
    assert g.metric == "wer" and g.score > 0


def test_wer_threshold():
    ref = {"transcript": "one two three four five six seven eight nine ten"}
    one_wrong = ours(transcript="one two three four five six seven eight nine tin")
    three_wrong = ours(transcript="one two tree four fife six seven ate nine ten")
    assert audio.grade(item("audio", "speech", ""), one_wrong, ref).hit is True      # 0.10
    assert audio.grade(item("audio", "speech", ""), three_wrong, ref).hit is False   # 0.30


def test_wer_falls_back_to_answer_when_no_transcript_event():
    g = audio.grade(item("audio", "speech", ""), ours("the washer shows e21"), {"transcript": "the washer shows e21"})
    assert g.hit and g.score == 0.0


def test_empty_reference_transcript():
    assert audio.grade(item("audio", "speech", ""), ours(transcript=""), {"transcript": ""}).hit is True
    assert audio.grade(item("audio", "speech", ""), ours(transcript="hello"), {"transcript": ""}).hit is False


def test_speech_question_is_answer_fuzzy_with_wer_note():
    g = audio.grade(item("audio", "speech", "What does the washer show?"),
                    ours("The washer shows error E21.", "speech", transcript="the washer shows e21"),
                    {"answer": "error E21", "transcript": "the washer shows e21"})
    assert g.metric == "fuzzy" and g.hit and g.score >= 80
    assert "wer=0.00" in g.note


def test_speech_wrong_answer_misses():
    g = audio.grade(item("audio", "speech", "What colour?"), ours("It is blue.", "speech"), {"answer": "red"})
    assert g.metric == "fuzzy" and not g.hit


# ---------------------------------------------------------------- sounds
def test_sound_top1_hit():
    g = audio.grade(item("audio", "sounds"), ours(sound_labels=["dog barking", "rain", "beep"]), {"answer": "dog"})
    assert (g.metric, g.hit) == ("top1", True) and g.note == "top3_hit=true"


def test_sound_top3_only():
    g = audio.grade(item("audio", "sounds"), ours(sound_labels=["dog barking", "rain", "beep"]), {"answer": "beep"})
    assert (g.metric, g.hit, g.note) == ("top1", False, "top3_hit=true")


def test_sound_miss():
    g = audio.grade(item("audio", "sound"), ours(sound_labels=["rain", "wind", "thunder"]), {"answer": "dog"})
    assert not g.hit and g.note == "top3_hit=false"


def test_sound_vocab_label_with_comma():
    """Our labels look like 'beep, bleep'; a reference 'beep' matches it."""
    g = audio.grade(item("audio", "sounds"), ours(sound_labels=["beep, bleep", "busy signal", "ping"]), {"answer": "beep"})
    assert g.hit


def test_sound_reference_list_of_synonyms():
    g = audio.grade(item("audio", "sounds"), ours(sound_labels=["chirp, tweet", "wind", "rain"]),
                    {"answer": ["bird", "chirp"]})
    assert g.hit


def test_sound_no_labels_is_a_miss():
    g = audio.grade(item("audio", "sounds"), ours(refusal="model_unavailable"), {"answer": "dog"})
    assert not g.hit and g.note == "top3_hit=false"


def test_sound_decided_by_item_not_our_route():
    """We routed it as speech; the item says it's a sound, so it's graded as a sound."""
    g = audio.grade(item("audio", "sounds"), ours("hello there", "speech", sound_labels=[]), {"answer": "dog"})
    assert g.metric == "top1"


def test_sound_when_subtype_unknown_uses_our_route():
    g = audio.grade(item("audio", ""), ours(question_type="sound", sound_labels=["dog barking"]), {"answer": "dog"})
    assert g.metric == "top1" and g.hit


# ---------------------------------------------------------------- video
def test_video_direction():
    g = video.grade(item("video"), ours("Right. The square moves right.", "motion", modality="video"),
                    {"answer": "right"})
    assert (g.metric, g.hit) == ("direction", True)


def test_video_direction_uses_first_word():
    g = video.grade(item("video"), ours("It moves left, then right.", "motion", modality="video"), {"answer": "right"})
    assert not g.hit


@pytest.mark.parametrize(("answer", "ref"), [
    ("It turns counterclockwise.", "counterclockwise"),
    ("The drum spins anticlockwise.", "counterclockwise"),
    ("The ball rolls towards the camera.", "toward"),
    ("It moves upward.", "up"),
])
def test_video_direction_synonyms(answer, ref):
    assert video.grade(item("video"), ours(answer, "motion", modality="video"), {"answer": ref}).hit


def test_counterclockwise_is_not_clockwise():
    g = video.grade(item("video"), ours("It turns counterclockwise.", "motion", modality="video"),
                    {"answer": "clockwise"})
    assert not g.hit


def test_video_count():
    g = video.grade(item("video"), ours("3. three people", "count", modality="video"), {"answer": 3})
    assert (g.metric, g.hit) == ("count_exact", True)


@pytest.mark.parametrize(("answer", "hit"), [("Three people walk by.", True), ("4 people", False),
                                             ("I can't tell.", False)])
def test_video_count_words_and_misses(answer, hit):
    assert video.grade(item("video"), ours(answer, "count", modality="video"), {"answer": "3"}).hit is hit


def test_video_other_is_fuzzy():
    g = video.grade(item("video"), ours("A red car parks next to a tree.", "describe", modality="video"),
                    {"answer": "red car parks next to tree"})
    assert g.metric == "fuzzy" and g.hit


def test_missing_reference_answer_is_a_miss_not_a_crash():
    g = video.grade(item("video"), ours("x", modality="video"), {"something_else": 1})
    assert not g.hit and "no reference" in g.note
    g = audio.grade(item("audio", "sounds"), ours(sound_labels=["dog"]), {})
    assert not g.hit and "no reference" in g.note
