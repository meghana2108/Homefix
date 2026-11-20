"""The single entry point for the API, the CLI and eval.

handle(): converting -> upload limits -> normalize -> empty check -> safety -> router -> pipeline.
Every stream ends with exactly one Final (latency_ms set here). A refusal or error comes right
before it. A crash anywhere becomes Error(retryable=True); the next request is unaffected.
Converted files live in a per-request temp folder that is deleted when the stream ends.
"""

from __future__ import annotations

import importlib
import re
import shutil
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path, PurePath

from app.contracts import (
    MESSAGES,
    Attachment,
    Ctx,
    Error,
    Event,
    Final,
    Modality,
    PipelineRequest,
    QuestionType,
    Refusal,
    Stage,
    Status,
    UnsupportedFile,
    final_for,
)
from app.media.convert import normalize
from app.models.memory import MemoryManager
from app.models.ollama_client import OllamaBackend
from app.router import route
from app.safety import refusal_for
from app.safety_semantic import check_all
from app.settings import load_profile


def build_ctx(profile_name: str | None = None) -> Ctx:
    profile = load_profile(profile_name)
    return Ctx(profile, MemoryManager(profile, OllamaBackend()),
               deadline_s=profile.server.model_call_timeout_s)


class _Stop(Exception):
    """Internal: a refusal or error ended the flow before a pipeline ran."""

    def __init__(self, event: Refusal | Error, modality: Modality = "none", question_type: QuestionType = "none"):
        self.event, self.modality, self.question_type = event, modality, question_type


def _size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0  # missing file -> normalize says "That file is empty."


def _convert(files: list[Path], names: list[str], ctx: Ctx, workdir: Path) -> Iterator[Event | Attachment]:
    server = ctx.profile.server
    if len(files) > server.max_files:
        raise _Stop(Refusal(reason="unsupported_file", message=MESSAGES["too_many_files"]))
    limit = server.max_file_mb * 1024 * 1024
    if any(_size(f) > limit for f in files):
        raise _Stop(Refusal(reason="too_large", message=MESSAGES["too_large"]))
    for f, name in zip(files, names, strict=True):
        try:
            att = normalize(f, name, ctx.profile, workdir)
        except UnsupportedFile as e:
            raise _Stop(Refusal(reason="unsupported_file", message=str(e))) from e
        for note in att.notes:
            yield Status(stage="converting", detail=note)
        yield att


AUTO_MANUAL = "auto"
# A photo goes to the manual only when the question is about a problem: an error, a code, blinking, or
# what to do. Naming an appliance is not enough ("What temperature is the thermostat set to?" is a photo question).
_PROBLEM_Q = re.compile(
    r"\b(error|code|codes|blink\w*|flash\w*|beep\w*|alarm|broken|won'?t|doesn'?t|not working|fix|problem|wrong|"
    r"manual|what (should|do|can) i do|what does (this|that|it) mean|mean)\b", re.IGNORECASE)
# Words that say nothing about which manual fits.
_FILLER = frozenset(
    ["a", "an", "the", "and", "or", "to", "of", "for", "on", "in", "at", "is", "it", "my", "me", "i", "you", "your", "this", "that", "what", "how", "do", "does", "did", "can", "should", "will", "with", "from", "who", "when", "where", "why", "which", "shows", "show", "set", "up", "off", "guide", "manual", "quick", "user", "unit", "apartment"])


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _FILLER and len(w) > 1}


def _stems(words: set[str]) -> set[str]:
    return {w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words}


def manual_candidates(message: str, manuals: list[dict]) -> list[dict]:
    """The manuals that best fit a question with no file: by name first, then by what their pages say.
    One manual when there is a clear winner; several when they tie; all of them when none fits."""
    words = _words(message)
    by_name = [(len(words & _words(f"{m['id'].replace('_', ' ')} {m['title']}")), m) for m in manuals]
    top = max(n for n, _ in by_name)
    if top:
        return [m for n, m in by_name if n == top]
    from app.pipelines import text

    stems = _stems(words)
    by_text = []
    for m in manuals:
        try:
            _, pages = text.load_manual(m["id"])
        except (OSError, RuntimeError, ValueError):
            pages = []
        by_text.append((len(stems & _stems(_words(" ".join(pages)))), m))
    top = max(n for n, _ in by_text)
    return [m for n, m in by_text if n == top] if top else list(manuals)


def resolve_manual(manual_id: str | None, message: str, attachments: list[Attachment]) -> str | None:
    """manual_id as given, or for "auto": the manual that fits the question, "auto" when HomeFix can't tell
    yet, or None.

    auto uses a manual for a single photo whose question is about a problem (an error, a code, what to do), and
    for a question with no attachment (which would otherwise be refused). Never for sound, video or an attached
    document. A manual named in the question wins (filler words don't count). Otherwise a photo stays "auto"
    and the code on its display picks the manual (pipelines/homefix.py), and a text question goes to the manual
    whose pages mention it, or stays "auto" so HomeFix asks which appliance it is. Never a silent first pick.
    """
    if manual_id != AUTO_MANUAL:
        return manual_id
    from app.pipelines.homefix import list_manuals

    manuals = list_manuals()
    if not manuals:
        return None
    if attachments and (len(attachments) != 1 or attachments[0].kind != "image"
                        or not _PROBLEM_Q.search(message)):
        return None
    if len(manuals) == 1:
        return manuals[0]["id"]
    if attachments:
        words = _words(message)
        named = [m for m in manuals if words & _words(f"{m['id'].replace('_', ' ')} {m['title']}")]
        return manual_candidates(message, named)[0]["id"] if named else AUTO_MANUAL
    fits = manual_candidates(message, manuals)
    return fits[0]["id"] if len(fits) == 1 else AUTO_MANUAL


def _flow(message: str, files: list[Path], manual_id: str | None, ctx: Ctx, names: list[str],
          attachments: list[Attachment] | None, workdir: Path, state: dict) -> Iterator[Event]:
    yield Status(stage="converting")
    if attachments is None:
        attachments = []
        for item in _convert(files, names, ctx, workdir):
            if isinstance(item, Attachment):
                attachments.append(item)
            else:
                yield item

    text = message.strip()
    if not text and not attachments:
        raise _Stop(Refusal(reason="empty_input", message=MESSAGES["empty_input"]))

    state["stage"] = "safety_check"
    yield Status(stage="safety_check")
    hit = check_all(text)  # the regex, then the meaning net (it can only add a stop)
    if hit:
        raise _Stop(refusal_for(hit))

    if text:
        from app.intent import intent_of

        state["intent"] = intent_of(text)  # the word rule or the meaning (cached vector, shared with safety)
    state["stage"] = "routing"
    yield Status(stage="routing")
    asked_auto = manual_id == AUTO_MANUAL
    manual_id = resolve_manual(manual_id, text, attachments)
    r = route(text, attachments, manual_id)
    if manual_id == AUTO_MANUAL and not attachments and r.modality == "text":  # several manuals fit: ask
        from app.clarify import manual_clarify
        from app.pipelines.homefix import list_manuals

        fits = manual_candidates(text, list_manuals())
        c = manual_clarify(text, fits)
        yield c
        yield final_for(ctx, "text", "doc_qa", c.question)
        return
    if asked_auto and manual_id and manual_id != AUTO_MANUAL and r.modality in ("text", "homefix"):
        # say so only when the answer uses it; for "auto" the homefix pipeline says which manual the code picked
        from app.pipelines.homefix import list_manuals

        title = next((m["title"] for m in list_manuals() if m["id"] == manual_id), manual_id)
        yield Status(stage="routing", detail=f"Using the manual: {title}")
    if r.refusal:
        raise _Stop(r.refusal, r.modality, r.question_type)
    if r.note:
        yield Status(stage="routing", detail=r.note)
    state["modality"], state["question_type"] = r.modality, r.question_type
    if r.modality == "code":
        try:
            ctx.memory.prefetch("coder")  # no-op on lite
        except Exception:  # noqa: BLE001, S110 - prefetch is only a speed-up
            pass

    module = importlib.import_module(f"app.pipelines.{r.modality}")
    req = PipelineRequest(text, attachments, r.question_type, manual_id)
    yield from module.run(req, ctx)
    if r.modality == "code" and ctx.profile.swap:  # the coder pushed the brain out: bring it back now
        ctx.memory.restore("brain")


def handle(message: str, files: list[Path], manual_id: str | None, ctx: Ctx,
           original_names: list[str] | None = None,
           attachments: list[Attachment] | None = None) -> Iterator[Event]:
    """Run one request. `attachments`, when given, skips conversion (eval's inline documents)."""
    t0 = time.perf_counter()
    files = [Path(f) for f in files]
    names = [PurePath(n).name for n in original_names] if original_names else [f.name for f in files]
    if len(names) != len(files):
        names = [f.name for f in files]
    workdir = Path(tempfile.mkdtemp(prefix="homefix_conv_"))
    state: dict = {"stage": "converting", "modality": "none", "question_type": "none"}
    final: Final | None = None

    def stamp(f: Final) -> Final:
        return f.model_copy(update={"latency_ms": int((time.perf_counter() - t0) * 1000),
                                    "intent": state.get("intent")})

    try:
        try:
            for ev in _flow(message, files, manual_id, ctx, names, attachments, workdir, state):
                if isinstance(ev, Final):
                    final = final or ev  # keep the first; a pipeline must send only one
                    continue
                if isinstance(ev, Status):
                    state["stage"] = ev.stage
                yield ev
        except _Stop as stop:
            yield stop.event
            final = final_for(ctx, stop.modality, stop.question_type)
        except Exception:  # noqa: BLE001 - any crash becomes a message; the app keeps serving
            stage: Stage = state["stage"]
            where = state["modality"] if state["modality"] != "none" else stage.replace("_", " ")
            yield Error(stage=stage, message=MESSAGES["pipeline_crash"].format(modality=where), retryable=True)
            final = final_for(ctx, state["modality"], state["question_type"])
        yield stamp(final or final_for(ctx, state["modality"], state["question_type"]))
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
