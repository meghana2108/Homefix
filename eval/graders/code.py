"""Code grader (docs/EVAL.md): "pass@1", hit when our code passes the item's test file in the sandbox.

The module name our code is imported as comes from the test file's first non-stdlib import
(default "solution"). Reading the test file's text for that is the only file access.

HumanEval-style test files (the practice pack's format) don't import our code and have no test_
function: just check(candidate) and a top-level check(<name>) call. For those, a copy in a temp folder
gets "from <module> import *" and the call moved into test_check(), so pytest collects one test. If the
file has no top-level call, the reference's entry_point names the function. The pack file isn't changed.
"""

from __future__ import annotations

import importlib.util
import re
import sys
import tempfile
from pathlib import Path

from app.code.sandbox import run_test_file
from eval.types import GradeResult, PackItem, RunRecord

_IMPORT = re.compile(r"^\s*(?:from\s+(\w+)\s+import|import\s+(\w+))", re.MULTILINE)


def _installed(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ValueError, ImportError):
        return True


def _module_name(test_path: Path) -> str:
    text = test_path.read_text(encoding="utf-8", errors="replace")
    for m in _IMPORT.finditer(text):
        name = m.group(1) or m.group(2)
        if name not in sys.stdlib_module_names and not _installed(name):
            return name
    return "solution"


_TEST_FN = re.compile(r"^def test_", re.MULTILINE)
_CHECK_FN = re.compile(r"^def check\(", re.MULTILINE)
_CHECK_CALL = re.compile(r"^check\((\w+)\)[ \t]*$\n?", re.MULTILINE)


def humaneval_wrapper(text: str, module: str, entry_point: str | None) -> str | None:
    """A collectable pytest file for a HumanEval-style test, or None when the file is a normal pytest file."""
    if _TEST_FN.search(text) or not _CHECK_FN.search(text):
        return None
    names = _CHECK_CALL.findall(text) or ([entry_point] if entry_point and entry_point.isidentifier() else [])
    if not names:
        return None
    body = _CHECK_CALL.sub("", text).rstrip()
    calls = "".join(f"    check({n})\n" for n in names)
    return f"from {module} import *  # noqa: F403\n\n{body}\n\n\ndef test_check():\n{calls}"


def grade(item: PackItem, ours: RunRecord, ref: dict) -> GradeResult:
    def miss(note: str) -> GradeResult:
        return GradeResult(item.id, "pass@1", 0.0, False, note)

    if not ours.code or not ours.code.strip():
        return miss("no code")
    raw = item.meta.get("test_path")
    test_path = Path(raw) if raw else None
    if test_path is None or not test_path.is_file():
        return miss("no test file")
    module = _module_name(test_path)
    wrapped = humaneval_wrapper(test_path.read_text(encoding="utf-8", errors="replace"), module,
                                ref.get("entry_point"))
    try:
        if wrapped is None:
            result = run_test_file(ours.code, test_path, module, timeout_s=10)
        else:
            with tempfile.TemporaryDirectory() as tmp:
                copy = Path(tmp) / test_path.name
                copy.write_text(wrapped, encoding="utf-8")
                result = run_test_file(ours.code, copy, module, timeout_s=10)
    except ValueError:
        return miss("bad module name")
    return GradeResult(item.id, "pass@1", 1.0 if result.passed else 0.0, bool(result.passed))
