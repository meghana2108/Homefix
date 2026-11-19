"""Eval seams: one adapter knows the pack format; only eval/grade.py opens the reference answers.

Every pack item here is invented for the test (hard rule 1: no pack content in the repo).
"""

import json

import pytest

from eval import grade, pack
from eval.grade import grade_run, load_refs, refs_available
from eval.pack import load_items, to_attachments
from eval.types import REF_KEYS, GradeResult, PackItem, RunRecord, norm

FAKE_ITEMS = [
    {"id": "fake-img-1", "modality": "image", "question": "How many cups?", "file": "media/cups.jpg"},
    {"id": "fake-aud-1", "modality": "audio", "question": "What is this sound?", "file": "media/beep.wav",
     "subtype": "sound"},
    {"id": "fake-txt-1", "modality": "text", "question": "When is rent due?",
     "context": "Rent is due on the first of the month."},
    {"id": "fake-code-1", "modality": "code", "question": "def add(a, b):\n    \"\"\"Add.\"\"\""},
]


def write_pack(tmp_path, items, wrap=None, refs=None):
    data = items if wrap is None else {wrap: items}
    (tmp_path / pack.ITEMS_FILE).write_text(json.dumps(data))
    (tmp_path / "code" / "tests").mkdir(parents=True, exist_ok=True)
    (tmp_path / "code" / "tests" / "fake-code-1_test.py").write_text("from solution import add\n")
    if refs is not None:
        (tmp_path / grade.ANSWERS_FILE).write_text(json.dumps(refs))
    return tmp_path


def record(item_id, modality, answer="x", **kw):
    base = {"run_id": "r1", "item_id": item_id, "modality": modality, "question_type": "none", "answer": answer,
                "refusal_reason": None, "code": None, "sound_labels": [], "latency_ms": 10, "peak_mem_gb": 1.0,
                "profile": "lite", "model": None}
    base.update(kw)
    return RunRecord(**base)


def test_load_items_list(tmp_path):
    items = load_items(write_pack(tmp_path, FAKE_ITEMS))
    assert [i.id for i in items] == ["fake-img-1", "fake-aud-1", "fake-txt-1", "fake-code-1"]
    assert [i.modality for i in items] == ["image", "audio", "text", "code"]
    img = items[0]
    assert img.path == tmp_path / "media/cups.jpg" and img.question == "How many cups?"
    assert items[1].meta["subtype"] == "sound"


@pytest.mark.parametrize("wrap", ["items", "data"])
def test_load_items_wrapped(tmp_path, wrap):
    assert len(load_items(write_pack(tmp_path, FAKE_ITEMS, wrap=wrap))) == 4


def test_load_items_dict_by_id(tmp_path):
    by_id = {it["id"]: {k: v for k, v in it.items() if k != "id"} for it in FAKE_ITEMS}
    (tmp_path / pack.ITEMS_FILE).write_text(json.dumps(by_id))
    assert [i.id for i in load_items(tmp_path)] == [it["id"] for it in FAKE_ITEMS]


def test_modality_synonyms(tmp_path):
    items = [{"id": "s1", "modality": "Speech", "question": "q", "file": "a.wav"},
             {"id": "s2", "type": "sounds", "question": "q", "file": "b.wav"}]
    got = load_items(write_pack(tmp_path, items))
    assert [(i.modality, i.meta["subtype"]) for i in got] == [("audio", "speech"), ("audio", "sounds")]


def test_unknown_modality_names_the_item(tmp_path):
    with pytest.raises(ValueError, match="fake-x-1"):
        load_items(write_pack(tmp_path, [{"id": "fake-x-1", "modality": "smell", "question": "q"}]))


def test_inline_document_becomes_attachment(tmp_path):
    txt = load_items(write_pack(tmp_path, FAKE_ITEMS))[2]
    assert txt.path is None and txt.meta["inline_document"] == "Rent is due on the first of the month."
    atts = to_attachments(txt)
    assert atts[0].path is None and atts[0].kind == "document" and atts[0].original_name == "fake-txt-1.txt"
    assert atts[0].pages == ["Rent is due on the first of the month."]


def test_file_items_have_no_prefilled_attachments(tmp_path):
    assert to_attachments(load_items(write_pack(tmp_path, FAKE_ITEMS))[0]) is None


def test_code_item_finds_its_test_file(tmp_path):
    code = load_items(write_pack(tmp_path, FAKE_ITEMS))[3]
    assert code.meta["test_path"] == tmp_path / "code/tests/fake-code-1_test.py"
    assert code.question.startswith("def add(")


def test_refs_and_grade_run_with_stubs(tmp_path):
    refs = [{"id": "fake-img-1", "answer": "3"}, {"id": "fake-aud-1", "answer": "beep"}]
    p = write_pack(tmp_path, FAKE_ITEMS, refs=refs)
    assert refs_available(p)
    loaded = load_refs(p)
    assert loaded["fake-img-1"]["answer"] == "3"
    items = {i.id: i for i in load_items(p)}
    out = grade_run([record("fake-img-1", "image"), record("fake-aud-1", "audio")], items, loaded)
    assert [g.item_id for g in out] == ["fake-img-1", "fake-aud-1"]
    assert all(isinstance(g, GradeResult) for g in out)
    assert not any(g.metric in ("grader_error", "missing_ref", "unknown_item") for g in out)
    assert out[1].metric == "top1"  # fake-aud-1 is a sound item (A9's audio grader)


def test_refs_dict_format(tmp_path):
    p = write_pack(tmp_path, FAKE_ITEMS, refs={"fake-img-1": {"answer": "3"}})
    assert load_refs(p)["fake-img-1"] == {"answer": "3"}


def test_no_refs(tmp_path):
    assert not refs_available(write_pack(tmp_path, FAKE_ITEMS))


def test_grade_run_never_crashes(tmp_path, monkeypatch):
    p = write_pack(tmp_path, FAKE_ITEMS, refs=[{"id": "fake-img-1", "answer": "3"}])
    items = {i.id: i for i in load_items(p)}
    from eval.graders import image

    def boom(item, ours, ref):
        raise KeyError("answer")
    monkeypatch.setattr(image, "grade", boom)
    out = grade_run([record("fake-img-1", "image"), record("fake-aud-1", "audio"), record("ghost", "image")],
                    items, load_refs(p))
    assert [g.metric for g in out] == ["grader_error", "missing_ref", "unknown_item"]
    assert all(isinstance(g, GradeResult) and not g.hit for g in out)


@pytest.mark.parametrize("modality", ["image", "audio", "text", "code", "video"])
def test_grader_stubs(modality):
    import importlib

    mod = importlib.import_module(f"eval.graders.{modality}")
    if "STUB" not in (mod.__doc__ or ""):
        pytest.skip("grader replaced")
    g = mod.grade(
        PackItem("fake-1", modality, "q", None, {}), record("fake-1", modality), {})
    assert g == GradeResult(item_id="fake-1", metric="todo", score=0.0, hit=False, note="not built")


@pytest.mark.parametrize(("text", "expected"), [
    ("The Red, Kettle!", "red kettle"),
    ("  An   apple a day ", "apple day"),
    ("Error E21.", "error e21"),
    ("", ""),
])
def test_norm(text, expected):
    assert norm(text) == expected


def test_ref_keys_defined():
    assert "answer" in REF_KEYS


def test_real_pack_loads(pack_dir):
    items = load_items(pack_dir)
    assert items and all(i.id for i in items)
    assert {i.modality for i in items} <= {"image", "audio", "text", "code", "video"}
