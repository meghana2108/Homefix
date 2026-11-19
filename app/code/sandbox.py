"""Run generated code in a locked-down subprocess: temp cwd, minimal env, no sockets,
no stdin, hard timeout, whole process group killed on timeout."""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from app.contracts import MESSAGES

MARKER = "__HOMEFIX__"
RAW_CAP = 200_000
TAIL = 1_500

BLOCK = '''
import socket as _s
def _blocked(*a, **k):
    raise OSError("network disabled")
class _Blocked:
    def __init__(self, *a, **k):
        raise OSError("network disabled")
_s.socket = _Blocked
_s.create_connection = _blocked
_s.getaddrinfo = _blocked
'''

PRELUDE = (
    "import sys, os, json, doctest\n"
    "sys.path.insert(0, os.getcwd())\n"
    + BLOCK
    + "import solution\n"
    "r = doctest.testmod(solution, verbose=False)\n"
    f"print({MARKER!r} + json.dumps({{'attempted': r.attempted, 'failed': r.failed}}))\n"
)


@dataclass
class SandboxResult:
    passed: bool
    tests_run: int
    failures: int
    output: str
    timed_out: bool


def _run(cmd: list[str], tmp: str, timeout_s: float) -> tuple[int | None, str, bool]:
    env = {"PATH": os.environ.get("PATH", ""), "HOME": tmp, "PYTHONHASHSEED": "0"}
    proc = subprocess.Popen(
        cmd, cwd=tmp, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, start_new_session=True,
    )
    timed_out = False
    try:
        out, _ = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        out, _ = proc.communicate()
    text = (out or b"")[:RAW_CAP * 4].decode("utf-8", "replace")
    # Keep the end of a capped stream, which holds the marker or the traceback.
    return proc.returncode, text[-RAW_CAP:], timed_out


def _timeout_result(timeout_s: float) -> SandboxResult:
    return SandboxResult(False, 0, 0, MESSAGES["code_timeout"].format(s=int(timeout_s)), True)


def run_doctests(code: str, files: dict[str, Path], timeout_s: float) -> SandboxResult:
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "solution.py").write_text(code)
        for name, src in files.items():
            shutil.copy(src, Path(tmp, name))
        _, text, timed_out = _run([sys.executable, "-I", "-c", PRELUDE], tmp, timeout_s)
    if timed_out:
        return _timeout_result(timeout_s)
    attempted = failed = None
    kept = []
    for line in text.splitlines():
        if line.startswith(MARKER):
            try:
                data = json.loads(line[len(MARKER):])
                attempted, failed = int(data["attempted"]), int(data["failed"])
            except (ValueError, KeyError):
                kept.append(line)
        else:
            kept.append(line)
    output = "\n".join(kept)[-TAIL:]
    if attempted is None:  # crashed before doctest finished (syntax error, import error, ...)
        return SandboxResult(False, 0, 0, output, False)
    if attempted == 0:
        return SandboxResult(False, 0, 0, MESSAGES["no_examples"], False)
    return SandboxResult(failed == 0, attempted, failed, output, False)


def run_test_file(code: str, test_file: Path, module_name: str, timeout_s: float) -> SandboxResult:
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, f"{module_name}.py").write_text(code)
        shutil.copy(test_file, Path(tmp, Path(test_file).name))
        Path(tmp, "conftest.py").write_text(BLOCK)
        rc, text, timed_out = _run(
            [sys.executable, "-I", "-m", "pytest", "-q", "-p", "no:cacheprovider",
             Path(test_file).name],
            tmp, timeout_s,
        )
    if timed_out:
        return _timeout_result(timeout_s)
    passed_n = int(m.group(1)) if (m := re.search(r"(\d+) passed", text)) else 0
    failed_n = int(m.group(1)) if (m := re.search(r"(\d+) (?:failed|error)", text)) else 0
    return SandboxResult(rc == 0, passed_n + failed_n, failed_n, text[-TAIL:], False)
