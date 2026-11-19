"""handle(): convert -> empty check -> safety -> router -> pipeline, ending in exactly one final.
A crash in one pipeline becomes an error card, and the next request still works."""

import time
from pathlib import Path

import pytest

from app import orchestrate
from app.contracts import (
    Attachment,
    Error,
    Final,
    PipelineRequest,
    Refusal,
    Status,
    Token,
    final_for,
)
from app.orchestrate import build_ctx, handle
from app.pipelines import image
from tests import media_fixtures as mf


def finals(events):
    return [e for e in events if isinstance(e, Final)]


@pytest.fixture
def spy_image(monkeypatch):
    """Replace the image pipeline; record what it receives."""
    seen = []

    def run(req, ctx):
        seen.append(req)
        assert all(a.path is None or a.path.exists() for a in req.attachments)
        yield Status(stage="generating")
        yield Token(text="4. Four mugs.")
        yield final_for(ctx, "image", req.question_type, "4. Four mugs.", "brain")
    monkeypatch.setattr(image, "run", run)
    return seen


def test_empty_input(ctx_full):
    ev = list(handle("", [], None, ctx_full))
    assert ev[0] == Status(stage="converting")
    assert ev[-2] == Refusal(reason="empty_input", message="Type a question or attach a file.")
    assert isinstance(ev[-1], Final)
    assert (ev[-1].answer, ev[-1].modality, ev[-1].question_type, ev[-1].profile) == ("", "none", "none", "full")


def test_whitespace_only_is_empty(ctx_full):
    assert list(handle("   \n", [], None, ctx_full))[-2].reason == "empty_input"


def test_safety_before_model(ctx_full, fake_brain):
    fake_brain()
    t0 = time.perf_counter()
    ev = list(handle("I smell burning plastic from the dryer", [], "washer", ctx_full))
    assert time.perf_counter() - t0 < 0.1
    assert ev[-2].type == "refusal" and ev[-2].reason == "safety" and ev[-2].category == "smoke_fire"
    assert fake_brain.calls == []
    assert ev[-1].latency_ms < 100
    assert [e.stage for e in ev if isinstance(e, Status)] == ["converting", "safety_check"]


def test_benign_lookalike_is_not_safety(ctx_full, fake_brain):
    ev = list(handle("smoke detector keeps chirping", [], "washer", ctx_full))
    assert not any(isinstance(e, Refusal) and e.reason == "safety" for e in ev)


def test_too_many_files(ctx_full, tmp_path):
    files = [mf.make_jpeg(tmp_path / f"{i}.jpg") for i in range(5)]
    ev = list(handle("how many", files, None, ctx_full))
    assert ev[-2] == Refusal(reason="unsupported_file", message="Attach up to 4 files at a time.")


def test_too_large(ctx_full, tmp_path, monkeypatch):
    monkeypatch.setattr(ctx_full.profile.server, "max_file_mb", 0)
    f = tmp_path / "a.txt"
    f.write_text("x")
    ev = list(handle("what?", [f], None, ctx_full))
    assert ev[-2] == Refusal(reason="too_large",
                             message="That file is over 200 MB. Try a shorter clip or a smaller photo.")


def test_unsupported_file(ctx_full, tmp_path):
    f = tmp_path / "setup.exe"
    f.write_bytes(b"MZ")
    ev = list(handle("", [f], None, ctx_full))
    assert ev[-2] == Refusal(reason="unsupported_file",
                             message="I can't open .exe files. Try a photo, audio, video, PDF, Word, text or CSV file.")
    assert len(finals(ev)) == 1


def test_original_names_decide_type(ctx_full, tmp_path, spy_image):
    """The API saves uploads under safe names; the original name carries the extension."""
    f = mf.make_jpeg(tmp_path / "upload_0")
    ev = list(handle("how many mugs?", [f], None, ctx_full, original_names=["IMG_2041.JPG"]))
    assert ev[-1].modality == "image" and ev[-1].question_type == "count"
    assert spy_image[0].attachments[0].original_name == "IMG_2041.JPG"


def test_photo_without_question_describes(ctx_full, tmp_path, spy_image):
    list(handle("", [mf.make_jpeg(tmp_path / "a.jpg")], None, ctx_full))
    assert spy_image[0].question_type == "describe"
    assert spy_image[0].message == ""


def test_message_stripped_and_manual_passed(ctx_full, tmp_path, spy_image):
    list(handle("  how many mugs?  ", [mf.make_jpeg(tmp_path / "a.jpg")], None, ctx_full))
    assert spy_image[0] == PipelineRequest("how many mugs?", spy_image[0].attachments, "count", None)


def test_converted_files_removed_after_stream(ctx_full, tmp_path, spy_image):
    src = mf.make_jpeg(tmp_path / "a.jpg")
    list(handle("how many", [src], None, ctx_full))
    converted = spy_image[0].attachments[0].path
    assert converted != src and not converted.exists()
    assert src.exists()  # the user's own file is never touched


def test_convert_notes_become_status(ctx_full, tmp_path, monkeypatch, spy_image):
    def fake_normalize(path, name, profile, workdir):
        return Attachment(path, "image", name, notes=["Used the first 120 s."])
    monkeypatch.setattr(orchestrate, "normalize", fake_normalize)
    ev = list(handle("what", [mf.make_jpeg(tmp_path / "a.jpg")], None, ctx_full))
    assert Status(stage="converting", detail="Used the first 120 s.") in ev


def test_route_note_becomes_status(ctx_full, tmp_path, monkeypatch):
    from app.pipelines import audio
    monkeypatch.setattr(audio, "run", lambda req, ctx: iter([final_for(ctx, "audio", req.question_type)]))
    files = [mf.make_sine_wav(tmp_path / "a.wav"), mf.make_jpeg(tmp_path / "b.jpg")]
    ev = list(handle("what is this", files, None, ctx_full))
    assert Status(stage="routing", detail="Only the first file was used.") in ev
    assert ev[-1].modality == "audio"


def test_route_refusal(ctx_full):
    ev = list(handle("how do I unclog a drain", [], None, ctx_full))
    assert ev[-2].reason == "no_document" and ev[-1].modality == "none"


def test_document_without_question(ctx_full, tmp_path):
    f = tmp_path / "lease.txt"
    f.write_text("Rent is due on the 1st.")
    ev = list(handle("", [f], None, ctx_full))
    assert ev[-2] == Refusal(reason="empty_input", message="Ask a question about the document.")


def test_crash_becomes_error_then_next_works(ctx_full, tmp_path, monkeypatch):
    def boom(req, ctx):
        yield Status(stage="generating")
        raise RuntimeError("model exploded")
    monkeypatch.setattr(image, "run", boom)
    ev = list(handle("how many", [mf.make_jpeg(tmp_path / "a.jpg")], None, ctx_full))
    assert ev[-2] == Error(stage="generating",
                           message="Something went wrong in the image step. Other questions still work.",
                           retryable=True)
    assert isinstance(ev[-1], Final) and ev[-1].modality == "image"
    doc = tmp_path / "manual.txt"
    doc.write_text("Clean the filter monthly.")
    nxt = list(handle("When should I clean the filter?", [doc], None, ctx_full))
    assert isinstance(nxt[-1], Final) and nxt[-1].modality == "text"


def test_crash_before_first_pipeline_status_uses_routing(ctx_full, tmp_path, monkeypatch):
    def boom(req, ctx):
        raise ValueError("bad")
        yield  # pragma: no cover
    monkeypatch.setattr(image, "run", boom)
    ev = list(handle("how many", [mf.make_jpeg(tmp_path / "a.jpg")], None, ctx_full))
    assert ev[-2].type == "error" and ev[-2].stage == "routing"


def test_crash_in_convert_is_error_not_exception(ctx_full, tmp_path, monkeypatch):
    def boom(*a, **kw):
        raise FileNotFoundError("ffmpeg")
    monkeypatch.setattr(orchestrate, "normalize", boom)
    ev = list(handle("hi", [mf.make_jpeg(tmp_path / "a.jpg")], None, ctx_full))
    assert ev[-2].type == "error" and ev[-2].stage == "converting" and ev[-2].retryable
    assert len(finals(ev)) == 1


def test_exactly_one_final(ctx_full, tmp_path, monkeypatch):
    monkeypatch.setattr(image, "run", lambda req, ctx: iter([Token(text="hi")]))
    ev = list(handle("how many", [mf.make_jpeg(tmp_path / "a.jpg")], None, ctx_full))
    assert len(finals(ev)) == 1 and ev[-1].modality == "image" and ev[-1].question_type == "count"


def test_extra_finals_collapsed(ctx_full, tmp_path, monkeypatch):
    def twice(req, ctx):
        yield final_for(ctx, "image", "count", "first")
        yield Token(text="late")
        yield final_for(ctx, "image", "count", "second")
    monkeypatch.setattr(image, "run", twice)
    ev = list(handle("how many", [mf.make_jpeg(tmp_path / "a.jpg")], None, ctx_full))
    assert len(finals(ev)) == 1 and ev[-1].answer == "first"


def test_latency_measured(ctx_full, tmp_path, monkeypatch):
    def slow(req, ctx):
        time.sleep(0.06)
        yield final_for(ctx, "image", "count", "4")
    monkeypatch.setattr(image, "run", slow)
    ev = list(handle("how many", [mf.make_jpeg(tmp_path / "a.jpg")], None, ctx_full))
    assert ev[-1].latency_ms >= 60


def test_prefilled_attachments_skip_convert(ctx_full, monkeypatch):
    """eval passes inline documents as attachments (path=None)."""
    monkeypatch.setattr(orchestrate, "normalize", lambda *a: pytest.fail("normalize called"))
    seen = []
    from app.pipelines import text
    monkeypatch.setattr(text, "run", lambda req, ctx: (seen.append(req), iter([]))[1])
    att = Attachment(None, "document", "item-7.txt", pages=["Clean the filter monthly."])
    ev = list(handle("When?", [], None, ctx_full, attachments=[att]))
    assert seen[0].attachments == [att] and ev[-1].modality == "text"


def test_code_prefetch_on_full(ctx_full, monkeypatch):
    from app.pipelines import code
    calls = []
    monkeypatch.setattr(ctx_full.memory, "prefetch", lambda role: calls.append(role))
    monkeypatch.setattr(code, "run", lambda req, ctx: iter([]))
    list(handle("write a python function to sum a list", [], None, ctx_full))
    assert calls == ["coder"]


def test_no_prefetch_for_other_routes(ctx_full, tmp_path, monkeypatch, spy_image):
    calls = []
    monkeypatch.setattr(ctx_full.memory, "prefetch", lambda role: calls.append(role))
    list(handle("how many", [mf.make_jpeg(tmp_path / "a.jpg")], None, ctx_full))
    assert calls == []


def test_build_ctx(monkeypatch):
    ctx = build_ctx("lite")
    assert ctx.profile.name == "lite" and ctx.deadline_s == ctx.profile.server.model_call_timeout_s
    assert ctx.memory.tag("brain") == ctx.profile.models.brain


def test_stage_order_for_normal_request(ctx_full, tmp_path, spy_image):
    ev = list(handle("how many", [mf.make_jpeg(tmp_path / "a.jpg")], None, ctx_full))
    stages = [e.stage for e in ev if isinstance(e, Status)]
    assert stages[:3] == ["converting", "safety_check", "routing"]


def test_missing_input_file_is_error_not_crash(ctx_full):
    ev = list(handle("hi", [Path("/nope/a.jpg")], None, ctx_full))
    assert isinstance(ev[-1], Final) and ev[-2].type in ("refusal", "error")
