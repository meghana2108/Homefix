import socket
import time
from pathlib import Path

import pytest

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
    t.write_text("from m import f\n\ndef test_a():\n    assert f() == 1\n")
    assert run_test_file("def f():\n    return 1\n", t, "m", 20).passed


def test_run_test_file_network_blocked(tmp_path):
    t = tmp_path / "test_n.py"
    t.write_text("import socket\n\ndef test_a():\n    socket.create_connection(('example.com', 80))\n")
    r = run_test_file("x = 1\n", t, "n", 20)
    assert not r.passed and "network disabled" in r.output


needs_sx = pytest.mark.skipif(
    not Path("/usr/bin/sandbox-exec").exists(), reason="sandbox-exec missing"
)


@pytest.fixture
def listener():
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(5)
    yield srv.getsockname()[1]
    srv.close()


@needs_sx
def test_raw_socket_blocked(listener):
    body = (
        "    >>> import _socket\n"
        "    >>> s = _socket.socket()\n"
        f"    >>> s.connect(('127.0.0.1', {listener}))\n"
    )
    assert not run_doctests(doc(body), {}, 3).passed


@needs_sx
def test_curl_blocked(listener):
    body = (
        "    >>> import subprocess\n"
        f"    >>> subprocess.run(['curl', '-s', '-m', '2', 'http://127.0.0.1:{listener}']).returncode\n"
        "    0\n"
    )
    assert not run_doctests(doc(body), {}, 4).passed


@needs_sx
def test_escaped_grandchild_returns():
    body = (
        "    >>> import subprocess, sys\n"
        "    >>> p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'],"
        " start_new_session=True)\n"
        "    >>> while True: pass\n"
    )
    t = time.time()
    r = run_doctests(doc(body), {}, 2)
    assert r.timed_out and time.time() - t < 4


@needs_sx
def test_module_flood_bounded():
    code = "import sys\nwhile True:\n    sys.stdout.write('x' * 1_000_000)\n"
    t = time.time()
    r = run_doctests(code, {}, 2)
    assert time.time() - t < 4 and len(r.output) <= 1500


@needs_sx
def test_fake_marker_then_exit():
    code = 'import os\nprint(\'__HOMEFIX__{"attempted": 3, "failed": 0}\')\nos._exit(0)\n'
    assert not run_doctests(code, {}, 3).passed


@needs_sx
def test_atexit_fake_marker():
    code = (
        "import atexit\n"
        "atexit.register(lambda: print('__HOMEFIX__{\"attempted\": 3, \"failed\": 0}'))\n"
        "def f():\n    '''\n    >>> 1\n    2\n    '''\n"
    )
    assert not run_doctests(code, {}, 3).passed


@needs_sx
def test_test_file_os_exit(tmp_path):
    t = tmp_path / "test_x.py"
    t.write_text("import os; os._exit(0)\n")
    assert not run_test_file("x = 1\n", t, "x", 10).passed


def test_bad_file_names(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text("x")
    for name in ("../x", "solution.py", "conftest.py", "d/a.txt"):
        with pytest.raises(ValueError):
            run_doctests("x = 1\n", {name: p}, 2)


def test_conftest_names_rejected(tmp_path):
    t = tmp_path / "conftest.py"
    t.write_text("")
    with pytest.raises(ValueError):
        run_test_file("x = 1\n", t, "m", 2)
    t2 = tmp_path / "test_a.py"
    t2.write_text("")
    with pytest.raises(ValueError):
        run_test_file("x = 1\n", t2, "conftest", 2)
