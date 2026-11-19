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
_FENCE = re.compile(r"```.*?```", re.DOTALL)
_DEF_LINE = re.compile(r"\b(def\s+[A-Za-z_]\w*\s*\(.*)$", re.MULTILINE)


def build_prompt(message: str, csv_preview: str | None, target: str | None,
                 last_output: str | None) -> str:
    parts = [message]
    if csv_preview:
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


def _data_files(req: PipelineRequest) -> tuple[dict[str, Path], str | None]:
    files: dict[str, Path] = {}
    preview = None
    for a in req.attachments:
        if a.kind != "data" or a.path is None:
            continue
        name = Path(a.original_name).name
        if (not name or name != a.original_name or name in ("solution.py", "conftest.py")
                or name in files):
            continue
        files[name] = a.path
        if preview is None and (body := _preview(a.path)):
            preview = f"File name: {name}\n{body}"
    return files, preview


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
    files, preview = _data_files(req)
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
            messages = [{"role": "system", "content": _SYSTEM},
                        {"role": "user",
                         "content": build_prompt(req.message, preview, target, last_output)}]
            raw = ollama_client.chat(tag, messages, num_ctx=ctx.memory.num_ctx("coder"),
                                     keep_alive=ctx.memory.keep_alive("coder"),
                                     timeout_s=ctx.deadline_s)
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
