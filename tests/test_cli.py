"""python -m app.cli runs the same handle() as the API and eval."""

import json
import subprocess
import sys

from app.settings import ROOT


def cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "app.cli", *args], capture_output=True, text=True, check=False,
                          cwd=ROOT, timeout=60)


def test_cli_empty():
    p = cli("")
    assert p.returncode == 0
    assert "Type a question or attach a file." in p.stdout
    assert "[status] converting" in p.stdout and "[final]" in p.stdout


def test_cli_safety_and_profile():
    p = cli("I smell gas", "--profile", "lite")
    assert p.returncode == 0 and "[refusal] safety" in p.stdout
    assert "This could be dangerous" in p.stdout


def test_cli_json_lines():
    p = cli("how do I unclog a drain", "--json")
    lines = [json.loads(ln) for ln in p.stdout.splitlines() if ln.strip()]
    assert lines[0]["type"] == "status" and lines[-1]["type"] == "final"
    assert lines[-2]["reason"] == "no_document"


def test_cli_missing_file():
    p = cli("what is this", "--file", "/nope/missing.jpg")
    assert p.returncode == 2 and "File not found: /nope/missing.jpg" in p.stderr


def test_cli_unsupported_file(tmp_path):
    f = tmp_path / "setup.exe"
    f.write_bytes(b"MZ")
    p = cli("", "--file", str(f))
    assert "I can't open .exe files." in p.stdout
