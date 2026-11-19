from pathlib import Path

import pytest

from app.contracts import (
    MESSAGES,
    Attachment,
    CodeResult,
    Final,
    ModelTimeout,
    ModelUnavailable,
    PipelineRequest,
    Refusal,
    Status,
)
from app.models import ollama_client
from app.pipelines import code

CSV = Path(__file__).resolve().parent.parent / "data" / "smartplug_fridge.csv"


ACF_SYSTEM = (
    "You write one short Python function for a renter. Reply with one line saying what it does, "
    "then one ```python code block holding only imports and the function. No print calls and no "
    "code outside the function. Put at least two doctest examples (>>> lines with the exact "
    "expected output) in the function's docstring. Use only the standard library. If a data file "
    "is named below, the function takes its file name as a string, and its doctest may call it "
    "with that exact name; compute expected values only from the lines shown. Otherwise use small "
    "literal values. Never invent other file names. Do not use the network."
)


def add_block(op="+"):
    return ("```python\ndef add(a, b):\n    \"\"\"\n    >>> add(1, 2)\n    3\n    >>> add(0, 0)\n"
            f"    0\n    \"\"\"\n    return a {op} b\n```")


GOOD = "Adds two numbers.\n" + add_block()
BAD = "First try.\n" + add_block("- 1 -")


def req(message="write add(a, b)", attachments=()):
    return PipelineRequest(message=message, attachments=list(attachments), question_type="code_gen")


def data(path=CSV, name="smartplug_fridge.csv"):
    return Attachment(path=path, kind="data", original_name=name)


def events(ctx, r):
    return list(code.run(r, ctx))


def result_of(evs):
    return next(e for e in evs if isinstance(e, CodeResult))


def prompt_text(call):
    return "\n".join(m["content"] for m in call["messages"])


def test_pass_first_try(ctx_full, fake_brain):
    fake_brain(GOOD)
    evs = events(ctx_full, req())
    r = result_of(evs)
    assert (r.passed, r.attempts, r.tests_run) == (True, 1, 2)
    fin = evs[-1]
    assert isinstance(fin, Final)
    assert fin.answer == "Adds two numbers."
    assert fin.model == ctx_full.memory.tag("coder")
    assert "def add" in r.code


def test_retry_after_fail(ctx_full, fake_brain):
    fake_brain(BAD, GOOD)
    r = result_of(events(ctx_full, req()))
    assert r.attempts == 2 and r.passed
    assert "Failed example" in prompt_text(fake_brain.calls[1])


def test_no_code_block_twice(ctx_full, fake_brain):
    fake_brain("I can't do that", "I can't do that")
    r = result_of(events(ctx_full, req()))
    assert (r.passed, r.attempts, r.output_tail) == (False, 2, "No code block found.")


def test_csv_preview_in_prompt(ctx_full, fake_brain):
    fake_brain(GOOD)
    events(ctx_full, req(attachments=[data()]))
    p = prompt_text(fake_brain.calls[0])
    assert "timestamp,watts" in p
    assert sum(1 for ln in p.splitlines() if ln.startswith("2026-")) == 5
    assert "inline list" in p and "Never open, read or name any file" in p


def test_csv_not_copied_into_sandbox(ctx_full, fake_brain, monkeypatch):
    seen = {}
    real = code.run_doctests

    def spy(src, files, timeout_s):
        seen["files"] = files
        return real(src, files, timeout_s)

    monkeypatch.setattr(code, "run_doctests", spy)
    fake_brain(GOOD)
    events(ctx_full, req(attachments=[data()]))
    assert seen["files"] == {}


def test_timeout(ctx_full, monkeypatch):
    def boom(*a, **k):
        raise ModelTimeout(MESSAGES["timeout"])

    monkeypatch.setattr(ollama_client, "chat", boom)
    evs = events(ctx_full, req())
    assert isinstance(evs[-2], Refusal) and evs[-2].reason == "timeout"
    assert isinstance(evs[-1], Final) and evs[-1].answer == ""


def test_target_name_kept(ctx_full, fake_brain):
    msg = "Count runs.\ndef count_long_runs(watts: list[float], threshold: float, min_len: int) -> int:"
    wrong = ("```python\ndef count_runs(watts, threshold, min_len):\n"
             "    \"\"\"\n    >>> count_runs([], 1, 1)\n    0\n    \"\"\"\n    return 0\n```")
    fake_brain(wrong, wrong)
    r = result_of(events(ctx_full, req(msg)))
    assert "Keep this exact function name and signature" in prompt_text(fake_brain.calls[0])
    assert r.output_tail == "Function count_long_runs not found."


def test_lite_swap_status(ctx_lite, fake_backend, fake_brain):
    fake_backend.loaded_tags = ["qwen3-vl:2b"]
    fake_brain(GOOD)
    first = events(ctx_lite, req())[0]
    assert isinstance(first, Status) and first.stage == "loading_model"


def test_ollama_down(ctx_full, monkeypatch):
    def boom(*a, **k):
        raise ModelUnavailable(MESSAGES["ollama_down"])

    monkeypatch.setattr(ollama_client, "chat", boom)
    evs = events(ctx_full, req())
    assert isinstance(evs[-2], Refusal) and evs[-2].reason == "model_unavailable"
    assert isinstance(evs[-1], Final) and evs[-1].answer == ""


def test_invalid_data_name_skipped(ctx_full, fake_brain):
    fake_brain(GOOD)
    r = result_of(events(ctx_full, req(attachments=[data(name="../x.csv")])))
    assert r.passed
    assert "timestamp" not in prompt_text(fake_brain.calls[0])


@pytest.mark.model
def test_real_golden_g6(ctx_full):
    msg = "Write a function that averages the fridge's watts per hour"
    evs = events(ctx_full, req(msg, [data()]))
    r = result_of(evs)
    assert r.passed is True, r.output_tail
    assert r.tests_run >= 2


def test_non_csv_requests_keep_the_original_prompt(ctx_full, fake_brain):
    fake_brain(GOOD, GOOD)
    events(ctx_full, req("write add(a, b)"))
    msgs = fake_brain.calls[0]["messages"]
    assert msgs == [{"role": "system", "content": ACF_SYSTEM},
                    {"role": "user", "content": "write add(a, b)"}]
    msg = "def add(x):\n    ..."
    events(ctx_full, req(msg))
    msgs = fake_brain.calls[1]["messages"]
    assert msgs[0]["content"] == ACF_SYSTEM
    assert msgs[1]["content"] == (
        msg + "\n\nKeep this exact function name and signature: def add(x): (name: add).")


def test_json_data_file_keeps_original_behaviour(ctx_full, fake_brain, monkeypatch, tmp_path):
    f = tmp_path / "up.bin"
    f.write_text('{"a": 1}\n')
    seen = {}
    real = code.run_doctests

    def spy(src, files, timeout_s):
        seen["files"] = files
        return real(src, files, timeout_s)

    monkeypatch.setattr(code, "run_doctests", spy)
    fake_brain(GOOD)
    events(ctx_full, req(attachments=[data(f, "plugs.json")]))
    p = prompt_text(fake_brain.calls[0])
    assert "lines: list[str]" not in p
    assert "Open it by the exact name given" in p and "File name: plugs.json" in p
    assert seen["files"] == {"plugs.json": f}
