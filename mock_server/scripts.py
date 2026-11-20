"""Canned event scripts for the mock server. Built from app.contracts so they can't drift.

script_for(message, filenames, manual_id) picks the first scenario whose trigger matches and
returns [(delay_s, event), ...]. Every script ends with exactly one Final.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import PurePath

from app.contracts import (
    MESSAGES,
    Citation,
    Clarify,
    ClarifyOption,
    CodeResult,
    Error,
    Event,
    Final,
    Frames,
    Modality,
    QuestionType,
    Refusal,
    SoundLabel,
    SoundLabels,
    Status,
    Token,
    Transcript,
)
from app.safety import SAFETY_MESSAGE

Step = tuple[float, Event]
Scenario = Callable[[str, list[str], str | None], list[Step]]

BRAIN = "qwen3-vl:8b-instruct"
CODER = "qwen2.5-coder:3b"
CLAP = "laion/clap-htsat-unfused"

AUDIO_EXT = {".wav", ".mp3", ".m4a"}
VIDEO_EXT = {".mp4", ".mov"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".bmp", ".gif"}
BLOCKED_EXT = {".exe", ".zip"}

PASSING_CODE = '''def hourly_average(path: str) -> dict[str, float]:
    r"""Average watts per hour from a smart-plug CSV.

    >>> import csv, tempfile, os
    >>> p = os.path.join(tempfile.mkdtemp(), "t.csv")
    >>> _ = open(p, "w").write("timestamp,watts\\n2026-11-09T00:00,100\\n2026-11-09T00:30,120\\n")
    >>> hourly_average(p)
    {'2026-11-09T00': 110.0}
    >>> hourly_average(p)['2026-11-09T00'] > 0
    True
    """
    import csv
    sums: dict[str, list[float]] = {}
    with open(path) as f:
        for row in csv.DictReader(f):
            sums.setdefault(row["timestamp"][:13], []).append(float(row["watts"]))
    return {h: sum(v) / len(v) for h, v in sums.items()}
'''

FAILING_CODE = '''def count_long_runs(watts: list[float], threshold: float, min_len: int) -> int:
    """
    >>> count_long_runs([0, 120, 130, 0, 125, 0], 100, 2)
    1
    >>> count_long_runs([150, 150, 150], 100, 3)
    1
    >>> count_long_runs([], 100, 1)
    0
    """
    runs, above = 0, False
    for w in watts:
        if w > threshold and not above:
            runs += 1
        above = w > threshold
    return runs
'''

FAILING_OUTPUT = """**********************************************************************
File "solution.py", line 3, in solution.count_long_runs
Failed example:
    count_long_runs([0, 120, 130, 0, 125, 0], 100, 2)
Expected:
    1
Got:
    2
**********************************************************************
1 items had failures:
   1 of   3 in solution.count_long_runs
***Test Failed*** 1 failures."""


def _ext(name: str) -> str:
    return PurePath(name).suffix.lower()


def _tokens(text: str) -> list[Step]:
    """Split into word chunks (spaces kept), 0.1-0.2 s apart, like a streaming brain."""
    words = text.split(" ")
    chunks = [w + " " for w in words[:-1]] + [words[-1]]
    return [(0.1 + 0.1 * (i % 2), Token(text=c)) for i, c in enumerate(chunks)]


def _final(steps: list[Step], modality: Modality, question_type: QuestionType,
           answer: str = "", model: str | None = None) -> list[Step]:
    delay = 0.1
    total_ms = round((sum(d for d, _ in steps) + delay) * 1000)
    final = Final(answer=answer, modality=modality, question_type=question_type,
                  latency_ms=total_ms, profile="full", model=model)
    return [*steps, (delay, final)]


def _front(*stages: str) -> list[Step]:
    """The status chips every real request starts with."""
    return [(0.1, Status(stage="converting")), (0.1, Status(stage="safety_check")),
            *[(0.2, Status(stage=s)) for s in stages]]


# ---------------------------------------------------------------- scenarios
def safety(message: str, files: list[str], manual_id: str | None) -> list[Step]:
    m = message.lower()
    category = "gas" if "gas" in m else "smoke_fire" if "burning" in m else "sparks"
    steps = [(0.1, Status(stage="converting")), (0.1, Status(stage="safety_check")),
             (0.1, Refusal(reason="safety", message=SAFETY_MESSAGE, category=category))]
    return _final(steps, "none", "none")


def unsupported(message: str, files: list[str], manual_id: str | None) -> list[Step]:
    bad = next((f for f in files if _ext(f) in BLOCKED_EXT), files[0] if files else "file.bin")
    ext = _ext(bad).lstrip(".") or "bin"
    steps = [(0.2, Status(stage="converting")),
             (0.1, Refusal(reason="unsupported_file", message=MESSAGES["unsupported_ext"].format(ext=ext)))]
    return _final(steps, "none", "none")


def empty(message: str, files: list[str], manual_id: str | None) -> list[Step]:
    steps = [(0.1, Status(stage="converting")),
             (0.1, Refusal(reason="empty_input", message=MESSAGES["empty_input"]))]
    return _final(steps, "none", "none")


def crash(message: str, files: list[str], manual_id: str | None) -> list[Step]:
    steps = [*_front("routing", "generating"),
             (1.0, Error(stage="generating", message=MESSAGES["pipeline_crash"].format(modality="image"),
                         retryable=True))]
    return _final(steps, "image", "qa")


def _code(passed: bool) -> list[Step]:
    steps = [*_front("routing"),
             (1.5, Status(stage="loading_model", detail=f"loading {CODER}", ms=6400)),
             (0.3, Status(stage="generating", detail=CODER)),
             (1.2, Status(stage="running_code"))]
    if passed:
        result = CodeResult(code=PASSING_CODE, passed=True, tests_run=2, failures=0,
                            output_tail="2 passed.", attempts=1)
        answer = "This function averages the fridge's watts for each hour."
    else:
        result = CodeResult(code=FAILING_CODE, passed=False, tests_run=3, failures=1,
                            output_tail=FAILING_OUTPUT, attempts=2)
        answer = ""
    return _final([*steps, (0.5, result)], "code", "code_gen", answer, CODER)


def code_fail(message: str, files: list[str], manual_id: str | None) -> list[Step]:
    return _code(passed=False)


def code_pass(message: str, files: list[str], manual_id: str | None) -> list[Step]:
    return _code(passed=True)


def speech(message: str, files: list[str], manual_id: str | None) -> list[Step]:
    text = "The washer shows E21 and the water won't drain."
    answer = "She says the washer shows error E21 and the water won't drain."
    steps = [*_front("routing", "transcribing"),
             (1.0, Transcript(text=text, seconds=12.4)),
             (0.3, Status(stage="generating", detail=BRAIN)),
             *_tokens(answer)]
    return _final(steps, "audio", "speech", answer, BRAIN)


def sound(message: str, files: list[str], manual_id: str | None) -> list[Step]:
    labels = [SoundLabel(label="washing machine beeping", score=0.71),
              SoundLabel(label="beep", score=0.12), SoundLabel(label="alarm", score=0.05)]
    steps = [*_front("routing", "transcribing"),
             (0.6, Status(stage="labeling_sounds")),
             (0.8, SoundLabels(labels=labels, is_speech=False))]
    return _final(steps, "audio", "sound", "Most likely **washing machine beeping** (71%). Also possible: beep, alarm.\n\nLook for the appliance with a light or a code on its display. A few short beeps at the end of a cycle are usually normal. If a code is showing, send me a photo of the display.", CLAP)


def video(message: str, files: list[str], manual_id: str | None) -> list[Step]:
    timestamps = [round(i * 28.1 / 15, 1) for i in range(16)]
    answer = ("Frame 1 at t=0.0s shows the washer drum still. Through t=28.1s the drum does not "
              "turn, while the display keeps blinking.")
    steps = [*_front("routing"),
             (1.2, Status(stage="extracting_frames")),
             (0.2, Frames(timestamps=timestamps)),
             (1.0, Status(stage="generating", detail=BRAIN)),
             *_tokens(answer)]
    return _final(steps, "video", "describe", answer, BRAIN)


def not_in_document(message: str, files: list[str], manual_id: str | None) -> list[Step]:
    steps = [*_front("routing", "retrieving"),
             (1.0, Status(stage="generating", detail=BRAIN)),
             (1.0, Status(stage="verifying")),
             (0.1, Refusal(reason="not_in_document", message=MESSAGES["not_in_document"]))]
    return _final(steps, "text", "doc_qa")


def citation(message: str, files: list[str], manual_id: str | None) -> list[Step]:
    answer = "Clean the drain pump filter once a month."
    steps = [*_front("routing", "retrieving"),
             (1.0, Status(stage="generating", detail=BRAIN)),
             (1.0, Status(stage="verifying")),
             (0.2, Citation(quote="Clean the drain pump filter once a month to prevent error E21.",
                            page=12, source="washer_manual.pdf", score=100.0))]
    return _final(steps, "text", "doc_qa", answer, BRAIN)


def image(message: str, files: list[str], manual_id: str | None) -> list[Step]:
    answer = "4. Four mugs on the shelf."
    steps = [*_front("routing"), (0.8, Status(stage="generating", detail=BRAIN)), *_tokens(answer)]
    return _final(steps, "image", "count", answer, BRAIN)


def clarify(message: str, files: list[str], manual_id: str | None) -> list[Step]:
    seen = "8:32 COOKTOP ON Oven Light Start | Cancel Lock Control Hold 3 Sec"
    c = Clarify(question="I don't see an error code. What would you like to know? Tell me which appliance this is "
                         "and what you noticed, or pick one below.", seen=seen,
                options=[ClarifyOption(label="What does “COOKTOP ON” mean?",
                                       message='What does "COOKTOP ON" mean?'),
                         ClarifyOption(label="Read everything on it", message="What does the display say?"),
                         ClarifyOption(label="Describe the photo", message="Describe the photo.")])
    steps = [*_front("routing"), (0.8, Status(stage="generating", detail=BRAIN)), (0.1, c)]
    return _final(steps, "image", "describe", c.question, BRAIN)


def no_document(message: str, files: list[str], manual_id: str | None) -> list[Step]:
    steps = [*_front("routing"),
             (0.1, Refusal(reason="no_document", message=MESSAGES["no_document"]))]
    return _final(steps, "none", "none")


SCENARIOS: dict[str, Scenario] = {
    "safety": safety, "unsupported": unsupported, "empty": empty, "crash": crash,
    "code_fail": code_fail, "code_pass": code_pass, "speech": speech, "sound": sound,
    "video": video, "not_in_document": not_in_document, "citation": citation,
    "image": image, "clarify": clarify, "no_document": no_document,
}


def _pick(message: str, files: list[str], manual_id: str | None) -> str:
    m = message.lower()
    exts = {_ext(f) for f in files}
    if any(w in m for w in ("gas", "burning", "sparks")):
        return "safety"
    if exts & BLOCKED_EXT:
        return "unsupported"
    if not m.strip() and not files:
        return "empty"
    if "crash" in m:
        return "crash"
    if "failing function" in m:
        return "code_fail"
    if "write" in m or ".csv" in exts:
        return "code_pass"
    if exts & AUDIO_EXT:
        return "speech" if "say" in m else "sound"
    if exts & VIDEO_EXT:
        return "video"
    if "not in" in m:
        return "not_in_document"
    if ".pdf" in exts or manual_id:
        return "citation"
    if exts & IMAGE_EXT:
        return "image" if "how many" in m else "clarify"
    return "no_document"


def script_for(message: str, filenames: list[str], manual_id: str | None) -> list[Step]:
    return SCENARIOS[_pick(message, filenames, manual_id)](message, filenames, manual_id)
