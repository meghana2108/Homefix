"""Run generated code in a locked-down subprocess: macOS sandbox-exec with all network
denied, temp cwd, minimal env, no stdin, hard timeout, process group killed on timeout.

Documented limits:
- This is not a container. The code can read and write any file the user can, by absolute path.
- A grandchild that calls setsid survives until it exits. It can no longer block the parent,
  because output goes to a file and we never wait on a pipe.
- Pass/fail is reported by the same process that runs the code, so a determined function can
  still lie. The nonce marker and exit code only stop accidental or naive fakes.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from app.contracts import MESSAGES

SANDBOX_EXEC = "/usr/bin/sandbox-exec"
PROFILE = "(version 1)(allow default)(deny network*)"
RAW_CAP = 200_000
TAIL = 1_500
UNAVAILABLE = "Code sandbox unavailable on this machine."

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
    "_nonce = os.environ['HOMEFIX_NONCE']\n"
    "del os.environ['HOMEFIX_NONCE']\n"
    "sys.path.insert(0, os.getcwd())\n"
    + BLOCK
    + "import solution\n"
    "r = doctest.testmod(solution, verbose=False)\n"
    "sys.stdout.flush()\n"
    "print('\\n__HOMEFIX_' + _nonce + '__' + json.dumps({'attempted': r.attempted, 'failed': r.failed}))\n"
)


@dataclass
class SandboxResult:
    passed: bool
    tests_run: int
    failures: int
    output: str
    timed_out: bool


def _run(cmd: list[str], tmp: str, timeout_s: float, nonce: str = "") -> tuple[int | None, str, bool]:
    env = {"PATH": os.environ.get("PATH", ""), "HOME": tmp, "PYTHONHASHSEED": "0"}
    if nonce:
        env["HOMEFIX_NONCE"] = nonce
    out_path = Path(tmp, ".homefix_out")
    timed_out = False
    with open(out_path, "wb") as f:
        proc = subprocess.Popen(
            [SANDBOX_EXEC, "-p", PROFILE, *cmd], cwd=tmp, env=env, stdin=subprocess.DEVNULL,
            stdout=f, stderr=subprocess.STDOUT, start_new_session=True,
        )
        try:
            proc.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
    with open(out_path, "rb") as f:
        size = f.seek(0, os.SEEK_END)
        f.seek(max(0, size - RAW_CAP))
        data = f.read(RAW_CAP)
    return proc.returncode, data.decode("utf-8", "replace"), timed_out


def _timeout_result(timeout_s: float) -> SandboxResult:
    return SandboxResult(False, 0, 0, MESSAGES["code_timeout"].format(s=int(timeout_s)), True)


def _unavailable() -> SandboxResult:
    return SandboxResult(False, 0, 0, UNAVAILABLE, False)


def run_doctests(code: str, files: dict[str, Path], timeout_s: float) -> SandboxResult:
    for name in files:
        if name != Path(name).name or name in ("solution.py", "conftest.py", ".homefix_out", ""):
            raise ValueError(f"bad file name: {name!r}")
    if not Path(SANDBOX_EXEC).exists():
        return _unavailable()
    nonce = secrets.token_hex(16)
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "solution.py").write_text(code)
        for name, src in files.items():
            shutil.copy(src, Path(tmp, name))
        rc, text, timed_out = _run([sys.executable, "-I", "-c", PRELUDE], tmp, timeout_s, nonce)
    if timed_out:
        return _timeout_result(timeout_s)
    prefix = f"__HOMEFIX_{nonce}__"
    lines = text.splitlines()
    nonempty = [i for i, ln in enumerate(lines) if ln.strip()]
    attempted = failed = None
    if nonempty and lines[nonempty[-1]].startswith(prefix):
        try:
            data = json.loads(lines[nonempty[-1]][len(prefix):])
            attempted, failed = int(data["attempted"]), int(data["failed"])
        except (ValueError, KeyError, TypeError):
            pass
        lines = lines[: nonempty[-1]]
    output = "\n".join(lines).rstrip()[-TAIL:]
    if attempted is None:  # crashed or exited early: syntax error, import error, os._exit, ...
        return SandboxResult(False, 0, 0, output, False)
    if attempted == 0:
        return SandboxResult(False, 0, 0, MESSAGES["no_examples"], False)
    return SandboxResult(failed == 0 and rc == 0, attempted, failed, output, False)


def run_test_file(code: str, test_file: Path, module_name: str, timeout_s: float) -> SandboxResult:
    test_name = Path(test_file).name
    if module_name == "conftest" or test_name == "conftest.py":
        raise ValueError("conftest is reserved")
    if not module_name.isidentifier():
        raise ValueError(f"bad module name: {module_name!r}")
    if not Path(SANDBOX_EXEC).exists():
        return _unavailable()
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, f"{module_name}.py").write_text(code)
        shutil.copy(test_file, Path(tmp, test_name))
        Path(tmp, "conftest.py").write_text(BLOCK)
        rc, text, timed_out = _run(
            [sys.executable, "-I", "-m", "pytest", "-q", "-p", "no:cacheprovider", test_name],
            tmp, timeout_s,
        )
    if timed_out:
        return _timeout_result(timeout_s)
    passed_n = sum(int(n) for n in re.findall(r"(\d+) passed", text))
    failed_n = sum(int(n) for n in re.findall(r"(\d+) (?:failed|errors?)\b", text))
    ran = passed_n + failed_n
    return SandboxResult(rc == 0 and ran > 0, ran, failed_n, text[-TAIL:], False)
