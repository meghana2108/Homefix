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
    top, *rest = labels
    answer = f"Sounds like: {', '.join([f'{top.label} ({top.score:.0%})', *(r.label for r in rest)])}."
    yield final_for(ctx, "audio", "sound", answer=answer, model=repo)


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
