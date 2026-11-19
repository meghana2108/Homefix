"""Run generated code in a locked-down subprocess: macOS sandbox-exec, temp cwd, minimal env,
no stdin, hard timeout, process group killed after every run.

What it does and does not do:
- Network is denied by the sandbox. Writes are confined to the run's temp dir. Reads are not
  confined: code can read any file the user can.
- Size caps: 50 MB per file (RLIMIT_FSIZE) and 200 MB per run. The run cap watches the free
  space of the disk holding the temp dir, so deleted-but-open files count. Other processes
  writing to the same disk during a run can trip it.
- A grandchild that calls setsid survives until it exits. It can't block the parent, because
  output goes to a file and we never wait on a pipe.
- Pass/fail comes from code running in the same process as the generated code. Code written
  to cheat (patching pytest or doctest, inspecting frames, reading its own process arguments
  to find the nonce) can fake a pass. The checks stop honest mistakes and casual fakes, not a
  deliberate adversary.
"""

from __future__ import annotations

import json
import os
import resource
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from app.contracts import MESSAGES

SANDBOX_EXEC = "/usr/bin/sandbox-exec"
RAW_CAP = 200_000
MAX_RUN_BYTES = 200_000_000
DISK_MSG = "Stopped: wrote more than 200 MB."
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
    "def _main():\n"
    "    nonce = os.environ.pop('HOMEFIX_NONCE')\n"
    "    sys.path.insert(0, os.getcwd())\n"
    + "".join("    " + ln + "\n" for ln in BLOCK.strip().splitlines())
    + "    import solution\n"
    "    r = doctest.testmod(solution, verbose=False)\n"
    "    sys.stdout.flush()\n"
    "    print('\\n__HOMEFIX_' + nonce + '__' + json.dumps({'attempted': r.attempted, 'failed': r.failed}))\n"
    "_main()\n"
    "del _main\n"
)

MAX_FILE_BYTES = 50_000_000
LAST_OUT_SIZE = 0  # test-only: size of the last run's output file


def _limit_file_size() -> None:
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_FILE_BYTES, MAX_FILE_BYTES))


def _profile(tmp: str) -> str:
    real = os.path.realpath(tmp)
    return (
        "(version 1)(allow default)(deny network*)(deny file-write*)"
        f'(allow file-write* (subpath "{real}") (literal "/dev/null"))'
    )


@dataclass
class SandboxResult:
    passed: bool
    tests_run: int
    failures: int
    output: str
    timed_out: bool


def _run(cmd: list[str], tmp: str, timeout_s: float, nonce: str = "") -> tuple[int | None, str, bool, bool]:
    """Run cmd in the sandbox. Output goes to a file outside tmp, which the child can't open for writing."""
    global LAST_OUT_SIZE
    env = {"PATH": os.environ.get("PATH", ""), "HOME": tmp, "PYTHONHASHSEED": "0"}
    if nonce:
        env["HOMEFIX_NONCE"] = nonce
    timed_out = disk_full = False
    base_free = shutil.disk_usage(tmp).free
    with tempfile.TemporaryDirectory() as outdir:
        out_path = Path(outdir, "out")
        with open(out_path, "wb") as f:
            proc = subprocess.Popen(
                [SANDBOX_EXEC, "-p", _profile(tmp), *cmd], cwd=tmp, env=env,
                stdin=subprocess.DEVNULL, stdout=f, stderr=subprocess.STDOUT,
                start_new_session=True, preexec_fn=_limit_file_size,  # noqa: PLW1509
            )
            deadline = time.monotonic() + timeout_s
            while True:
                try:
                    proc.wait(timeout=0.2)
                    break
                except subprocess.TimeoutExpired:
                    pass
                if base_free - shutil.disk_usage(tmp).free > MAX_RUN_BYTES:
                    disk_full = True
                    break
                if time.monotonic() >= deadline:
                    timed_out = True
                    break
            # Always kill the group, so background children don't outlive the run.
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
            LAST_OUT_SIZE = size
            f.seek(max(0, size - RAW_CAP))
            data = f.read(RAW_CAP)
    text = data.decode("utf-8", "replace")
    if proc.returncode == -signal.SIGXFSZ:
        text += "\nOutput or file size limit exceeded."
    return proc.returncode, text, timed_out, disk_full


def _timeout_result(timeout_s: float) -> SandboxResult:
    return SandboxResult(False, 0, 0, MESSAGES["code_timeout"].format(s=int(timeout_s)), True)


def _unavailable() -> SandboxResult:
    return SandboxResult(False, 0, 0, UNAVAILABLE, False)


def run_doctests(code: str, files: dict[str, Path], timeout_s: float) -> SandboxResult:
    for name in files:
        if name != Path(name).name or name in ("solution.py", "conftest.py", ""):
            raise ValueError(f"bad file name: {name!r}")
    if not Path(SANDBOX_EXEC).exists():
        return _unavailable()
    nonce = secrets.token_hex(16)
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "solution.py").write_text(code)
        for name, src in files.items():
            shutil.copy(src, Path(tmp, name))
        rc, text, timed_out, disk_full = _run(
            [sys.executable, "-I", "-c", PRELUDE], tmp, timeout_s, nonce
        )
    if disk_full:
        return SandboxResult(False, 0, 0, DISK_MSG, False)
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


CONFTEST = BLOCK + '''
import os as _os, json as _json, sys as _sys

def _make_hooks():
    nonce = _os.environ.pop("HOMEFIX_NONCE")
    box = {}

    def pytest_sessionfinish(session, exitstatus):
        stats = session.config.pluginmanager.get_plugin("terminalreporter").stats
        box["r"] = {
            "passed": len(stats.get("passed", [])),
            "failed": len(stats.get("failed", [])),
            "errors": len(stats.get("error", [])),
        }

    def pytest_unconfigure(config):
        if "r" in box:
            _sys.stdout.flush()
            print("\\n__HOMEFIX_" + nonce + "__" + _json.dumps(box["r"]))
            _sys.stdout.flush()

    return pytest_sessionfinish, pytest_unconfigure

pytest_sessionfinish, pytest_unconfigure = _make_hooks()
del _make_hooks
'''


def run_test_file(code: str, test_file: Path, module_name: str, timeout_s: float) -> SandboxResult:
    test_name = Path(test_file).name
    if module_name == Path(test_file).stem:
        raise ValueError("module name must differ from the test file name")
    if module_name == "conftest" or test_name == "conftest.py":
        raise ValueError("conftest is reserved")
    if not module_name.isidentifier():
        raise ValueError(f"bad module name: {module_name!r}")
    if not Path(SANDBOX_EXEC).exists():
        return _unavailable()
    nonce = secrets.token_hex(16)
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, f"{module_name}.py").write_text(code)
        shutil.copy(test_file, Path(tmp, test_name))
        Path(tmp, "conftest.py").write_text(CONFTEST)
        rc, text, timed_out, disk_full = _run(
            [sys.executable, "-I", "-m", "pytest", "-q", "-p", "no:cacheprovider", test_name],
            tmp, timeout_s, nonce,
        )
    if disk_full:
        return SandboxResult(False, 0, 0, DISK_MSG, False)
    if timed_out:
        return _timeout_result(timeout_s)
    prefix = f"__HOMEFIX_{nonce}__"
    lines = text.splitlines()
    nonempty = [i for i, ln in enumerate(lines) if ln.strip()]
    if not nonempty or not lines[nonempty[-1]].startswith(prefix):
        return SandboxResult(False, 0, 0, text[-TAIL:], False)
    try:
        d = json.loads(lines[nonempty[-1]][len(prefix):])
        passed_n, failed_n, errors_n = int(d["passed"]), int(d["failed"]), int(d["errors"])
    except (ValueError, KeyError, TypeError):
        return SandboxResult(False, 0, 0, text[-TAIL:], False)
    output = "\n".join(lines[: nonempty[-1]]).rstrip()[-TAIL:]
    bad = failed_n + errors_n
    return SandboxResult(rc == 0 and bad == 0 and passed_n > 0, passed_n + bad, bad, output, False)
