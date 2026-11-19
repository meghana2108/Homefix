"""eval.run / eval.report: every item goes through handle(); the summary has numbers only.

All items and answers here are invented (hard rule 1)."""

import csv
import json
import re

import pytest

from app.contracts import (
    CodeResult,
    Final,
    Refusal,
    SoundLabel,
    SoundLabels,
    Status,
    Token,
    Transcript,
)
from eval import grade, pack, report
from eval import run as er
from eval.types import GradeResult, PackItem, RunRecord

SECRET_Q = "How many zebras secretly hide here?"
SECRET_A = "SECRET-ANSWER-TEXT"


def final(answer="", modality="image", qtype="count", latency=1234, model="m"):
    return Final(answer=answer, modality=modality, question_type=qtype, latency_ms=latency, profile="lite",
                 model=model)


def rec(item_id, modality, latency=1000, refusal=None, answer=SECRET_A, qtype="count"):
    return RunRecord(run_id="r1", item_id=item_id, modality=modality, question_type=qtype, answer=answer,
                     refusal_reason=refusal, code=None, sound_labels=[], latency_ms=latency, peak_mem_gb=3.2,
                     profile="lite", model="m")


# ---------------------------------------------------------------- overrides
def test_apply_overrides(profile_lite):
    p = er.apply_overrides(profile_lite, ["text.quote_fuzz_threshold=85", "models.brain=gemma4:e4b",
                                          "video.frames=12"])
    assert p.text.quote_fuzz_threshold == 85 and p.models.brain == "gemma4:e4b" and p.video.frames == 12
    assert profile_lite.text.quote_fuzz_threshold == 92  # original untouched


@pytest.mark.parametrize("bad", ["text.nope=1", "nope=1", "models=x", "text.quote_fuzz_threshold"])
def test_unknown_setting(profile_lite, bad):
    with pytest.raises(SystemExit, match="Unknown setting|Use key.path=value"):
        er.apply_overrides(profile_lite, [bad])


def test_bad_value(profile_lite):
    with pytest.raises(SystemExit, match="Bad value for video.frames"):
        er.apply_overrides(profile_lite, ["video.frames=lots"])


def test_run_id_format():
    assert re.fullmatch(r"\d{8}-\d{4}-lite-image", er.make_run_id("lite", "image"))


# ---------------------------------------------------------------- run_items
@pytest.fixture
def fake_handle(monkeypatch):
    calls = []
    scripts = {}

    def handle(message, files, manual_id, ctx, original_names=None, attachments=None):
        calls.append({"message": message, "files": files, "names": original_names, "attachments": attachments})
        yield from scripts[len(calls) - 1]
    monkeypatch.setattr(er, "handle", handle)
    monkeypatch.setattr(er, "measure_gb", lambda: 2.5)
    return calls, scripts


def test_run_items(ctx_lite, tmp_path, fake_handle):
    calls, scripts = fake_handle
    img = PackItem("fake-img-1", "image", SECRET_Q, tmp_path / "a.jpg", {})
    txt = PackItem("fake-txt-1", "text", "When?", None, {"inline_document": "Rent is due monthly."})
    scripts[0] = [Status(stage="generating"), Token(text="4."), final("4. Four.", latency=6200)]
    scripts[1] = [Refusal(reason="not_in_document", message="The document doesn't contain the answer."),
                  final("", "text", "doc_qa", latency=900, model=None)]
    out = er.run_items([img, txt], ctx_lite, "r1")
    assert [r.item_id for r in out] == ["fake-img-1", "fake-txt-1"]
    assert out[0].answer == "4. Four." and out[0].latency_ms == 6200 and out[0].question_type == "count"
    assert out[0].peak_mem_gb == 2.5 and out[0].profile == "lite" and out[0].modality == "image"
    assert out[1].refusal_reason == "not_in_document" and out[1].latency_ms == 900
    assert calls[0]["files"] == [tmp_path / "a.jpg"] and calls[0]["names"] == ["a.jpg"]
    assert calls[0]["message"] == SECRET_Q and calls[0]["attachments"] is None
    assert calls[1]["files"] == [] and calls[1]["attachments"][0].pages == ["Rent is due monthly."]


def test_run_items_collects_payloads(ctx_lite, fake_handle):
    _, scripts = fake_handle
    scripts[0] = [Transcript(text="the washer shows e21", seconds=3.0), final("It shows E21.", "audio", "speech")]
    scripts[1] = [SoundLabels(labels=[SoundLabel(label="beep", score=0.6), SoundLabel(label="alarm", score=0.2)],
                              is_speech=False), final("Sounds like: beep", "audio", "sound")]
    scripts[2] = [CodeResult(code="def f(): pass", passed=True, tests_run=2, failures=0, output_tail="", attempts=1),
                  final("", "code", "code_gen")]
    items = [PackItem(f"fake-{i}", m, "q", None, {}) for i, m in enumerate(["audio", "audio", "code"])]
    out = er.run_items(items, ctx_lite, "r1")
    assert out[0].transcript == "the washer shows e21"
    assert out[1].sound_labels == ["beep", "alarm"]
    assert out[2].code == "def f(): pass"


def test_run_items_survives_a_crash_and_writes_as_it_goes(ctx_lite, tmp_path, fake_handle):
    _, scripts = fake_handle
    scripts[0] = None  # iterating None raises TypeError inside handle
    scripts[1] = [final("ok")]
    sink = tmp_path / "r1.jsonl"
    out = er.run_items([PackItem("a", "image", "q", None, {}), PackItem("b", "image", "q", None, {})],
                       ctx_lite, "r1", sink=sink)
    assert [r.refusal_reason for r in out] == ["error", None]
    assert [json.loads(ln)["item_id"] for ln in sink.read_text().splitlines()] == ["a", "b"]


def test_error_event_is_recorded(ctx_lite, fake_handle):
    from app.contracts import Error
    _, scripts = fake_handle
    scripts[0] = [Error(stage="generating", message="Something went wrong", retryable=True), final("")]
    assert er.run_items([PackItem("a", "image", "q", None, {})], ctx_lite, "r1")[0].refusal_reason == "error"


# ---------------------------------------------------------------- summary
def test_summarize_counts_and_no_text():
    records = [rec(f"i{k}", "image") for k in range(4)]
    graded = [GradeResult(f"i{k}", "count_exact", float(k < 3), k < 3) for k in range(4)]
    md = report.summarize(graded, records)
    assert "| count_exact | 3/4 |" in md
    assert SECRET_A not in md and SECRET_Q not in md


def test_summarize_top3_refusals_latency():
    records = [rec("s1", "audio", 1000), rec("s2", "audio", 3000),
               rec("t1", "text", 2000, refusal="not_in_document"),     # unanswerable, refused: right
               rec("t2", "text", 4000, refusal="not_in_document"),     # answerable, refused: wrong
               rec("t3", "text", 6000)]                                # unanswerable, answered: wrong
    graded = [GradeResult("s1", "top1", 100, True, "top3_hit=true"),
              GradeResult("s2", "top1", 10, False, "top3_hit=true"),
              GradeResult("t1", "refusal", 1, True), GradeResult("t2", "answer_match", 0, False),
              GradeResult("t3", "refusal", 0, False)]
    md = report.summarize(graded, records)
    assert "| top1 | 1/2 |" in md and "| top3 | 2/2 |" in md
    assert "Refusal precision 1/2" in md and "recall 1/2" in md
    assert "| audio | 2 | 2.0 s | 3.0 s |" in md   # p50 / p95 latency
    assert "Peak memory: 3.2 GB" in md


def test_summarize_without_grades():
    md = report.summarize([], [rec("i1", "image", 5000)])
    assert "not graded" in md and "| image | 1 | 5.0 s | 5.0 s |" in md


def test_summary_has_latency_targets():
    md = report.summarize([], [rec("i1", "image", 5000)])
    assert "Target p50" in md and "≤ 15 s" in md  # lite image target


# ---------------------------------------------------------------- end to end (fake pack, fake handle)
FAKE_ITEMS = [{"id": "fake-img-1", "modality": "image", "question": SECRET_Q, "file": "m/a.jpg"},
              {"id": "fake-img-2", "modality": "image", "question": "q2", "file": "m/b.jpg"},
              {"id": "fake-aud-1", "modality": "audio", "question": "q3", "file": "m/c.wav", "subtype": "sounds"}]


@pytest.fixture
def fake_pack(tmp_path, monkeypatch):
    d = tmp_path / "pack"
    d.mkdir()
    (d / pack.ITEMS_FILE).write_text(json.dumps(FAKE_ITEMS))
    results = tmp_path / "results"
    monkeypatch.setattr(er, "RESULTS", results)
    monkeypatch.setattr(report, "RESULTS", results)

    def handle(message, files, manual_id, ctx, original_names=None, attachments=None):
        if files and files[0].suffix == ".wav":
            yield SoundLabels(labels=[SoundLabel(label="dog barking", score=0.7)], is_speech=False)
            yield final("Sounds like: dog barking (70%).", "audio", "sound")
        else:
            yield final("3. Three zebras.")
    monkeypatch.setattr(er, "handle", handle)
    monkeypatch.setattr(er, "measure_gb", lambda: 1.0)
    return d, results


def test_main_without_answers(fake_pack):
    d, results = fake_pack
    run_id = er.main(["--profile", "lite", "--modality", "image", "--pack", str(d), "--no-grade"])
    lines = (results / "raw" / f"{run_id}.jsonl").read_text().splitlines()
    assert len(lines) == 2 and not (results / "raw" / f"{run_id}_graded.jsonl").exists()


def test_main_limit_per_modality(fake_pack):
    d, results = fake_pack
    run_id = er.main(["--profile", "lite", "--modality", "all", "--limit", "1", "--pack", str(d), "--no-grade"])
    ids = [json.loads(ln)["item_id"] for ln in (results / "raw" / f"{run_id}.jsonl").read_text().splitlines()]
    assert ids == ["fake-img-1", "fake-aud-1"]


def test_main_grades_and_report(fake_pack):
    d, results = fake_pack
    (d / grade.ANSWERS_FILE).write_text(json.dumps([{"id": "fake-img-1", "answer": "3"},
                                                    {"id": "fake-aud-1", "answer": "dog"}]))
    run_id = er.main(["--profile", "lite", "--modality", "all", "--pack", str(d)])
    graded = [json.loads(ln) for ln in (results / "raw" / f"{run_id}_graded.jsonl").read_text().splitlines()]
    metrics = {g["item_id"]: g["metric"] for g in graded}
    assert set(metrics) == {"fake-img-1", "fake-img-2", "fake-aud-1"}
    assert metrics["fake-img-2"] == "missing_ref" and metrics["fake-aud-1"] == "top1"
    assert metrics["fake-img-1"] not in ("grader_error", "missing_ref", "unknown_item")  # stub or M11's grader
    with open(results / "raw" / f"{run_id}_review.csv") as f:
        rows = list(csv.DictReader(f))
    assert {"item_id", "metric", "hit", "ours", "ref"} <= set(rows[0])
    out = report.main(["--run", run_id])
    md = out.read_text()
    assert out == results / "summary_lite.md"
    assert "| top1 | 1/1 |" in md and SECRET_Q not in md and "Three zebras" not in md


def test_main_needs_a_pack(monkeypatch, tmp_path):
    monkeypatch.delenv("PRACTICE_PACK_DIR", raising=False)
    monkeypatch.chdir(tmp_path)  # no .env here
    with pytest.raises(SystemExit, match="PRACTICE_PACK_DIR"):
        er.main(["--profile", "lite", "--modality", "image"])


def test_report_missing_run(fake_pack):
    with pytest.raises(SystemExit, match="No run"):
        report.main(["--run", "20260101-0000-lite-image"])


@pytest.mark.model
def test_real_pack_two_images(pack_dir, tmp_path, monkeypatch):
    monkeypatch.setattr(er, "RESULTS", tmp_path)
    run_id = er.main(["--profile", "lite", "--modality", "image", "--limit", "2", "--pack", str(pack_dir),
                      "--no-grade"])
    assert len((tmp_path / "raw" / f"{run_id}.jsonl").read_text().splitlines()) == 2


def test_regrade_a_finished_run(fake_pack, monkeypatch):
    """A grader fix shouldn't need a 30-minute re-run: --regrade grades the saved answers again."""
    d, results = fake_pack
    run_id = er.main(["--profile", "lite", "--modality", "all", "--pack", str(d), "--no-grade"])
    (d / grade.ANSWERS_FILE).write_text(json.dumps([{"id": "fake-aud-1", "reference_answer": "dog"}]))
    monkeypatch.setattr(er, "handle", lambda *a, **k: pytest.fail("regrade must not run the models"))
    assert er.main(["--regrade", run_id, "--pack", str(d)]) == run_id
    graded = [json.loads(ln) for ln in (results / "raw" / f"{run_id}_graded.jsonl").read_text().splitlines()]
    assert {g["item_id"]: g["hit"] for g in graded}["fake-aud-1"] is True


def test_regrade_missing_run(fake_pack):
    d, _ = fake_pack
    with pytest.raises(SystemExit, match="No run"):
        er.main(["--regrade", "20260101-0000-lite-all", "--pack", str(d)])
