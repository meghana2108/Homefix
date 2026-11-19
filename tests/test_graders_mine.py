"""Image, text and code graders. Invented items only; nothing from the practice pack."""

from __future__ import annotations

from eval.graders import code, image, text
from eval.types import GradeResult, PackItem, RunRecord


def _item(modality: str, **meta) -> PackItem:
    return PackItem(f"fake-{modality}-1", modality, "q", None, meta)


def _ours(modality: str, answer: str = "", qt: str = "", **kw) -> RunRecord:
    base = {
        "run_id": "r", "item_id": f"fake-{modality}-1", "modality": modality, "question_type": qt,
        "answer": answer, "refusal_reason": None, "code": None, "sound_labels": [],
        "latency_ms": 0, "peak_mem_gb": 0.0, "profile": "full", "model": None,
    }
    base.update(kw)
    return RunRecord(**base)


def test_image_count_hit_and_miss():
    it = _item("image")
    hit = image.grade(it, _ours("image", "4. four mugs", "count"), {"answer": "4"})
    miss = image.grade(it, _ours("image", "I can't tell.", "count"), {"answer": 4})
    assert isinstance(hit, GradeResult) and hit.metric == "count_exact" and hit.hit
    assert not miss.hit
    assert image.grade(it, _ours("image", "four", "count"), {"answer": ["4", "four"]}).hit


def test_image_fuzzy():
    r = image.grade(_item("image"), _ours("image", "a red kettle on a stove", "describe"),
                    {"answer": "red kettle on the stove"})
    assert r.metric == "fuzzy" and r.hit and r.score >= 80
    assert not image.grade(_item("image"), _ours("image", "a blue sofa", "describe"),
                           {"answer": "red kettle on the stove"}).hit


def test_text_answerable():
    it = _item("text")
    assert text.grade(it, _ours("text", "The deposit is $500, due at signing."),
                      {"answer": "$500", "answerable": True}).hit
    r = text.grade(it, _ours("text", "x", refusal_reason="not_in_document"),
                   {"answer": "$500", "answerable": True})
    assert r.metric == "answer_match" and not r.hit


def test_text_unanswerable():
    it = _item("text")
    ref = {"answerable": False}
    hit = text.grade(it, _ours("text", "", refusal_reason="not_in_document"), ref)
    assert hit.metric == "refusal" and hit.hit
    assert not text.grade(it, _ours("text", "It is 5 days."), ref).hit


def _test_file(tmp_path):
    p = tmp_path / "test_add.py"
    p.write_text("from solution import add\n\ndef test_add():\n    assert add(1, 2) == 3\n")
    return p


def test_code_pass_and_fail(tmp_path):
    it = _item("code", test_path=_test_file(tmp_path))
    ok = code.grade(it, _ours("code", code="def add(a, b):\n    return a + b\n"), {})
    bad = code.grade(it, _ours("code", code="def add(a, b):\n    return a - b\n"), {})
    assert ok.metric == "pass@1" and ok.hit
    assert not bad.hit


def test_code_missing_pieces(tmp_path):
    assert code.grade(_item("code", test_path=_test_file(tmp_path)), _ours("code"), {}).note == "no code"
    r = code.grade(_item("code", test_path=tmp_path / "nope.py"), _ours("code", code="x=1"), {})
    assert r.note == "no test file" and not r.hit
