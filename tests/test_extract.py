from app.code.extract import extract_code, find_target, stub_imports

CODE = "def foo(x):\n    return x\n"


def test_python_fence_among_prose():
    assert extract_code(f"Here you go:\n```python\n{CODE}```\nEnjoy.").strip() == CODE.strip()


def test_plain_fence():
    assert extract_code(f"```\n{CODE}```").strip() == CODE.strip()


def test_no_fence_valid_code():
    assert extract_code(CODE) == CODE


def test_prose_only():
    assert extract_code("Sorry, I can't help with that.") is None


def test_target_missing():
    assert extract_code(CODE, target_name="bar") is None


def test_target_present():
    assert extract_code(CODE, target_name="foo") is not None


def test_find_target():
    assert find_target('def count_runs(w: list[int]) -> int:\n    """...') == "count_runs"
    assert find_target("no code") is None


def test_stub_imports():
    msg = "import csv\nfrom math import sqrt\ndef f():\n    import os\n    return 1"
    assert stub_imports(msg) == ["import csv", "from math import sqrt", "import os"]
