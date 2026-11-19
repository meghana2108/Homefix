"""Audio pipeline: a voice note gets a transcript (and an answer if there's a question);
any other sound gets its top-3 labels. Danger in the words, or a loud smoke/CO alarm, gets the
fixed safety message and no model answer.

Router "sound" skips Whisper (faster, and Whisper invents words in beeps). Router "speech" or
"none" transcribes first; "none" counts as speech only with >= 3 words and a low mean
no_speech_prob. A "speech" clip with no words falls back to sound labels.
"""

from __future__ import annotations

from collections.abc import Iterator

from app.contracts import (
    MESSAGES,
    Attachment,
    Ctx,
    Event,
    ModelUnavailable,
    PipelineRequest,
    QuestionType,
    Refusal,
    SoundLabel,
    SoundLabels,
    Status,
    Transcript,
    final_for,
)
from app.models.clap import classify, load_vocab
from app.models.whisper import TranscriptResult, transcribe
from app.pipelines.common import collect, stream_brain
from app.safety import check, check_sound, refusal_for

MIN_SPEECH_WORDS = 3

SYSTEM = ("You answer questions about a voice recording using only its transcript. "
          "Answer in at most three short sentences. "
          "If the transcript doesn't contain the answer, reply exactly: I can't tell.")


def is_speech(question_type: QuestionType, tr: TranscriptResult, max_no_speech: float) -> bool:
    """Spec Pipelines > Audio, rule 2."""
    if question_type == "sound" or not tr.text.strip():
        return False
    if question_type == "speech":
        return True
    return len(tr.text.split()) >= MIN_SPEECH_WORDS and tr.mean_no_speech_prob < max_no_speech


def _prompt(tr: TranscriptResult, question: str) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f'Transcript of the recording ({tr.seconds:.1f} s):\n"""\n{tr.text}\n"""\n\n'
                                    f"Question: {question}"},
    ]


def _speech(req: PipelineRequest, ctx: Ctx, tr: TranscriptResult) -> Iterator[Event]:
    yield Transcript(text=tr.text, seconds=tr.seconds)
    hit = check(tr.text)
    if hit:
        yield refusal_for(hit)
        yield final_for(ctx, "audio", "speech")
        return
    if not req.message.strip():
        yield final_for(ctx, "audio", "speech", answer=tr.text, model=ctx.profile.models.whisper_file)
        return
    answer: list[str] = []
    was_refused = False
    for ev in collect(stream_brain(ctx, _prompt(tr, req.message.strip())), answer):  # stream live
        was_refused = was_refused or isinstance(ev, Refusal)
        yield ev
    if was_refused:
        yield final_for(ctx, "audio", "speech")
    else:
        yield final_for(ctx, "audio", "speech", answer="".join(answer).strip(), model=ctx.memory.tag("brain"))


CLOSE_CALL = 0.05  # top two this close: say they sound alike instead of picking one
# (words in any of the top labels, what to tell a renter next). First match only; plain code, no model.
NEXT_STEPS: list[tuple[tuple[str, ...], str]] = [
    (("smoke", "carbon monoxide", "fire alarm", "co alarm"),
     "If this could be a smoke or carbon monoxide alarm, don't wait: leave and call 911."),
    (("chirp",),
     "A single chirp every 30 to 60 seconds is usually a smoke alarm with a low battery. Tell maintenance."),
    (("drip", "water", "pour", "splash", "trickle", "gurgl", "rain", "drop"),
     ("If it's water you can't explain, look under the sinks and around the washer, and turn off the water "
     "valve if you find a leak. Then call maintenance.")),
    (("hiss",),
     "A hiss near a gas stove or heater can be a gas leak: leave and call the gas emergency line from outside."),
    (("beep", "microwave", "washing machine", "dishwasher", "dryer", "oven", "timer", "alarm clock"),
     ("Look for the appliance with a light or a code on its display. A few short beeps at the end of a cycle "
     "are usually normal. If a code is showing, send me a photo of the display.")),
]


def describe_sounds(labels: list[SoundLabel]) -> str:
    """The top labels in words: the most likely one (or a close call), the others, and a next step."""
    top, *rest = labels
    if rest and top.score - rest[0].score < CLOSE_CALL:
        lead = (f"Most likely **{top.label}** or **{rest[0].label}**: they sound alike to me "
                f"({top.score:.0%} and {rest[0].score:.0%}).")
        others = rest[1:]
    else:
        lead = f"Most likely **{top.label}** ({top.score:.0%})."
        others = rest
    parts = [lead + (f" Also possible: {', '.join(r.label for r in others)}." if others else "")]
    # the top label decides the hint; the others only when it has none
    hint = next((text for lb in labels for words, text in NEXT_STEPS if any(w in lb.label.lower() for w in words)), None)
    if hint:
        parts.append(hint)
    return "\n\n".join(parts)


def _sound(ctx: Ctx, att: Attachment) -> Iterator[Event]:
    yield Status(stage="labeling_sounds")
    repo = ctx.profile.models.clap
    try:
        labels = classify(att.path, repo, load_vocab(), top_k=ctx.profile.audio.top_k)
    except ModelUnavailable as e:
        yield Refusal(reason="model_unavailable", message=str(e))
        yield final_for(ctx, "audio", "sound")
        return
    yield SoundLabels(labels=labels, is_speech=False)
    hit = check_sound(labels, ctx.profile.audio.alarm_safety_min_score)
    if hit:
        yield refusal_for(hit)
        yield final_for(ctx, "audio", "sound")
        return
    yield final_for(ctx, "audio", "sound", answer=describe_sounds(labels), model=repo)


def run(req: PipelineRequest, ctx: Ctx) -> Iterator[Event]:
    att = next((a for a in req.attachments if a.kind == "audio" and a.path), None)
    if att is None:
        yield Refusal(reason="empty_input", message=MESSAGES["empty_input"])
        yield final_for(ctx, "audio", req.question_type)
        return

    if req.question_type == "sound":
        yield from _sound(ctx, att)
        return

    yield Status(stage="transcribing")
    try:
        tr = transcribe(att.path, ctx.profile.models.whisper_file)
    except ModelUnavailable as e:
        yield Refusal(reason="model_unavailable", message=str(e))
        yield final_for(ctx, "audio", req.question_type)
        return

    if is_speech(req.question_type, tr, ctx.profile.audio.speech_max_no_speech_prob):
        yield from _speech(req, ctx, tr)
    else:
        yield from _sound(ctx, att)
