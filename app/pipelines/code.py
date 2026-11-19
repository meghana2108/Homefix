"""Code pipeline: the coder model writes one function, the sandbox runs its doctests.

One automatic retry with the failure output. The UI shows the code and a pass/fail badge.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

from app.code.extract import extract_code, find_target, stub_imports
from app.code.sandbox import SandboxResult, run_doctests
from app.contracts import (
    MESSAGES,
    CodeResult,
    Ctx,
    Event,
    ModelTimeout,
    ModelUnavailable,
    PipelineRequest,
    Refusal,
    Status,
    final_for,
)
from app.models import ollama_client

_SYSTEM = (
    "You write one short Python function for a renter. Reply with one line saying what it does, "
    "then one ```python code block holding only imports and the function. No print calls and no "
    "code outside the function. Put at least two doctest examples (>>> lines with the exact "
    "expected output) in the function's docstring. Use only the standard library. If a data file "
    "is named below, the function takes its file name as a string, and its doctest may call it "
    "with that exact name; compute expected values only from the lines shown. Otherwise use small "
    "literal values. Never invent other file names. Do not use the network."
)
_SYSTEM_CSV = (
    "You write one short Python function for a renter. Reply with one line saying what it does, "
    "then one ```python code block holding only imports and the function. No print calls and no "
    "code outside the function. Put at least two doctest examples (>>> lines with the exact "
    "expected output) in the function's docstring. Use only the standard library. Do not use "
    "the network."
)
_CSV_RULES = (
    "The data is a CSV file. Write the function so it takes `lines: list[str]`, the CSV text "
    "lines including the header, and returns the result. Skip the header line and read each number by column position (split each line on a comma with no space after it), parsing with float(). In the "
    "doctest examples, pass a short inline list of 3 to 5 lines (the header plus rows) written "
    "right in the docstring, with your own made-up round numbers (like 100.0 and 200.0, not the real rows) so you can work out "
    "the exact answer by hand, and wrap the result in round(..., 2). Put each example call on ONE line of the docstring (no line breaks inside the call). Give two examples with "
    "different inline lists. Never open, read or name any file in the code or the examples. "
    "Example of the shape (your function name and numbers will differ):\n"
    '>>> round(f(["t,w", "a,100.0", "b,200.0", "c,300.0"]), 2)\n200.0\n'
    "The file starts like this (header and first rows):"
)
_FENCE = re.compile(r"```.*?```", re.DOTALL)
_DEF_LINE = re.compile(r"\b(def\s+[A-Za-z_]\w*\s*\(.*)$", re.MULTILINE)


def build_prompt(message: str, csv_preview: str | None, target: str | None,
                 last_output: str | None, *, csv: bool = False) -> str:
    """csv=True: csv_preview is the header + 5 rows of a .csv file and the function takes
    its lines. Otherwise csv_preview is the preview of another data file, opened by name."""
    parts = [message]
    if csv_preview and csv:
        parts.append(f"{_CSV_RULES}\n{csv_preview}")
    elif csv_preview:
        parts.append("The data file is in the current folder. Open it by the exact name given. "
                     f"It looks like this (first lines):\n{csv_preview}")
    if target:
        m = _DEF_LINE.search(message)
        sig = f": {m.group(1).strip()}" if m else ""
        parts.append(f"Keep this exact function name and signature{sig} (name: {target}).")
    if last_output:
        parts.append("Your last attempt failed with this output. Fix the function and "
                     f"reply again in the same format:\n{last_output}")
    return "\n\n".join(parts)


def _preview(path: Path) -> str | None:
    try:
        with path.open(encoding="utf-8", errors="replace") as f:
            lines = [ln.rstrip("\r\n") for _, ln in zip(range(6), f)]
    except OSError:
        return None
    return "\n".join(lines) or None


def _data_files(req: PipelineRequest) -> tuple[dict[str, Path], str | None, bool]:
    """(files for the sandbox, preview, preview_is_csv). A .csv is shown to the model as lines
    and not copied into the sandbox; any other data file is copied under its own name."""
    files: dict[str, Path] = {}
    csv_preview = other_preview = None
    seen: set[str] = set()
    for a in req.attachments:
        if a.kind != "data" or a.path is None:
            continue
        name = Path(a.original_name).name
        if (not name or name != a.original_name or name in ("solution.py", "conftest.py")
                or name in seen):
            continue
        seen.add(name)
        if name.lower().endswith(".csv"):
            if csv_preview is None:
                csv_preview = _preview(a.path)
        else:
            files[name] = a.path
            if other_preview is None and (body := _preview(a.path)):
                other_preview = f"File name: {name}\n{body}"
    if csv_preview:
        return files, csv_preview, True
    return files, other_preview, False


def _prose(raw: str) -> str:
    for line in _FENCE.sub("", raw).splitlines():
        if line.strip() and not line.strip().startswith("```"):
            return line.strip()
    return ""


def _refuse(ctx: Ctx, reason: str, message: str) -> Iterator[Event]:
    yield Refusal(reason=reason, message=message)  # type: ignore[arg-type]
    yield final_for(ctx, "code", "code_gen")


def run(req: PipelineRequest, ctx: Ctx) -> Iterator[Event]:
    cfg = ctx.profile.code
    target = find_target(req.message)
    files, preview, is_csv = _data_files(req)
    imports = stub_imports(req.message)
    max_attempts = 1 + cfg.max_retries
    last_output: str | None = None
    result: CodeResult | None = None
    raw = ""
    try:
        yield from ctx.memory.ensure("coder")
        tag = ctx.memory.tag("coder")
        for attempt in range(1, max_attempts + 1):
            yield Status(stage="generating", detail=tag)
            messages = [{"role": "system", "content": _SYSTEM_CSV if is_csv else _SYSTEM},
                        {"role": "user",
                         "content": build_prompt(req.message, preview, target, last_output,
                                             csv=is_csv)}]
            raw = ollama_client.chat(tag, messages, num_ctx=ctx.memory.num_ctx("coder"),
                                     keep_alive=ctx.memory.keep_alive("coder"),
                                     timeout_s=ctx.deadline_s, temperature=0.0, seed=7)
            code = extract_code(raw, target)
            if code is None:
                if target and extract_code(raw) is not None:
                    output = MESSAGES["function_missing"].format(name=target)
                else:
                    output = MESSAGES["no_code_block"]
                result = CodeResult(code="", passed=False, tests_run=0, failures=0,
                                    output_tail=output, attempts=attempt)
            else:
                yield Status(stage="running_code")
                full = "\n".join([*imports, code]) if imports else code
                res: SandboxResult = run_doctests(full, files, cfg.selfcheck_timeout_s)
                result = CodeResult(code=code, passed=res.passed, tests_run=res.tests_run,
                                    failures=res.failures, output_tail=res.output,
                                    attempts=attempt)
            if result.passed:
                break
            last_output = result.output_tail
    except ModelUnavailable as e:
        yield from _refuse(ctx, "model_unavailable", str(e))
        return
    except ModelTimeout:
        yield from _refuse(ctx, "timeout", MESSAGES["timeout"])
        return
    assert result is not None
    yield result
    yield final_for(ctx, "code", "code_gen", answer=_prose(raw), model=ctx.memory.tag("coder"))
