import time
from pathlib import Path

from app.code.sandbox import run_doctests, run_test_file

ROOT = Path(__file__).resolve().parent.parent


def add_code(op="+"):
    return (
        f'def add(a, b):\n    """\n    >>> add(1, 2)\n    3\n    >>> add(0, 0)\n    0\n    """\n'
        f"    return a {op} b\n"
    )


def doc(body):
    return f'def f():\n    """\n{body}\n    """\n    return 1\n'


def test_passing_doctests():
    r = run_doctests(add_code(), {}, 5)
    assert r.passed and r.tests_run == 2 and r.failures == 0


def test_failing_doctest():
    r = run_doctests(add_code("- 1 -"), {}, 5)
    assert not r.passed and r.failures == 2


def test_infinite_loop_times_out():
    t = time.time()
    r = run_doctests(doc("    >>> while True: pass\n"), {}, 2)
    assert r.timed_out and not r.passed
    assert r.output == "Timed out after 2 s."
    assert time.time() - t < 4


def test_network_disabled():
    r = run_doctests(
        doc('    >>> import socket; socket.create_connection(("example.com", 80))'), {}, 5
    )
    assert not r.passed and "network disabled" in r.output


def test_socket_class_blocked():
    r = run_doctests(doc("    >>> import socket; socket.socket()"), {}, 5)
    assert not r.passed and "network disabled" in r.output


def test_no_examples():
    r = run_doctests("def f():\n    return 1\n", {}, 5)
    assert not r.passed and r.output == "No examples to check."


def test_data_file_available():
    code = doc(
        "    >>> open('smartplug_fridge.csv').readline().strip()\n    'timestamp,watts'"
    )
    r = run_doctests(code, {"smartplug_fridge.csv": ROOT / "data/smartplug_fridge.csv"}, 5)
    assert r.passed


def test_cwd_is_temp():
    code = doc(f"    >>> import os; os.getcwd() == r'{ROOT}'\n    False")
    assert run_doctests(code, {}, 5).passed


def test_grandchild_killed_on_timeout():
    body = (
        "    >>> import subprocess, sys\n"
        "    >>> p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        "    >>> while True: pass\n"
    )
    t = time.time()
    r = run_doctests(doc(body), {}, 2)
    assert r.timed_out and time.time() - t < 4


def test_output_capped():
    r = run_doctests(doc("    >>> print('x' * 10_000_000)\n    y"), {}, 10)
    assert len(r.output) <= 1500


def test_input_fails_fast():
    t = time.time()
    r = run_doctests(doc("    >>> input()\n    ''"), {}, 5)
    assert not r.passed and time.time() - t < 3


def test_syntax_error():
    r = run_doctests("def f(:\n    pass\n", {}, 5)
    assert not r.passed and r.tests_run == 0 and "SyntaxError" in r.output


def test_run_test_file(tmp_path):
    t = tmp_path / "test_m.py"
    t.write_text("from m import f\n\ndef test_a():\n    assert f() == 1\n\ndef test_b():\n    assert f() == 2\n")
    r = run_test_file("def f():\n    return 1\n", t, "m", 20)
    assert not r.passed and r.tests_run == 2 and r.failures == 1
    r = run_test_file("def f():\n    return 1\n", tmp_path / "test_m.py", "m", 20)
    t.write_text("from m import f\n\ndef test_a():\n    assert f() == 1\n")
    assert run_test_file("def f():\n    return 1\n", t, "m", 20).passed


def test_run_test_file_network_blocked(tmp_path):
    t = tmp_path / "test_n.py"
    t.write_text("import socket\n\ndef test_a():\n    socket.create_connection(('example.com', 80))\n")
    r = run_test_file("x = 1\n", t, "n", 20)
    assert not r.passed and "network disabled" in r.output
