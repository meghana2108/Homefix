"""Code grader (docs/EVAL.md): "pass@1", hit when our code passes the item's test file in the sandbox.

The module name our code is imported as comes from the test file's first non-stdlib import
(default "solution"). Reading the test file's text for that is the only file access.
"""

from __future__ import annotations

import importlib.util
import re
import sys
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


def grade(item: PackItem, ours: RunRecord, ref: dict) -> GradeResult:
    def miss(note: str) -> GradeResult:
        return GradeResult(item.id, "pass@1", 0.0, False, note)

    if not ours.code or not ours.code.strip():
        return miss("no code")
    raw = item.meta.get("test_path")
    test_path = Path(raw) if raw else None
    if test_path is None or not test_path.is_file():
        return miss("no test file")
    try:
        result = run_test_file(ours.code, test_path, _module_name(test_path), timeout_s=10)
    except ValueError:
        return miss("bad module name")
    return GradeResult(item.id, "pass@1", 1.0 if result.passed else 0.0, bool(result.passed))
