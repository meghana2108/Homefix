import json
import os

import numpy as np
import pymupdf
import pytest

from app.contracts import (
    MESSAGES,
    Attachment,
    Citation,
    Final,
    ModelTimeout,
    ModelUnavailable,
    PipelineRequest,
    Refusal,
    Status,
    Token,
)
from app.models import embeddings, ollama_client
from app.pipelines import text

PAGES = [
    "Error E21 means the water did not drain. Clean the drain pump filter every month.",
    "To level the washer, turn the front feet. Use a spirit level on the lid.",
]


def doc(pages=PAGES, name="manual.pdf"):
    return Attachment(path=None, kind="document", original_name=name, pages=list(pages))


def req(q="how do I clean it", pages=PAGES, name="manual.pdf", **kw):
    return PipelineRequest(q, [doc(pages, name)], "doc_qa", **kw)


def reply(answer, quote, page):
    return json.dumps({"answer": answer, "quote": quote, "page": page})


def run(r, ctx):
    return list(text.run(r, ctx))


def of(events, cls):
    return [e for e in events if isinstance(e, cls)]


def test_verified_answer_cites_page(fake_brain, ctx_full):
    fake_brain(reply("Clean the drain pump filter.", "Clean the drain pump filter every month", 1))
    ev = run(req(), ctx_full)
    (c,) = of(ev, Citation)
    assert c.page == 1 and c.source == "manual.pdf"
    assert ev[-1].answer == "Clean the drain pump filter."
    assert not of(ev, Token)
    assert ev[-1].model == ctx_full.memory.tag("brain")
    call = fake_brain.calls[0]
    assert call["json_format"] is True and call["num_ctx"] == ctx_full.memory.num_ctx("brain")
    stages = [e.stage for e in of(ev, Status)]
    assert stages[-2:] == ["generating", "verifying"] or stages[-1] == "verifying"


def test_not_json_then_refuse(fake_brain, ctx_full):
    fake_brain("Sure! The answer is…", "still not json")
    ev = run(req(), ctx_full)
    assert ev[-2] == Refusal(reason="not_in_document", message="The document doesn't contain the answer.")
    assert ev[-1].answer == "" and isinstance(ev[-1], Final)
    assert len(fake_brain.calls) == 2


def test_retry_with_shorter_quote(fake_brain, ctx_full):
    fake_brain(reply("Clean the filter.", "Wash the pump strainer monthly", 1),
               reply("Clean the filter.", "Clean the drain pump filter every month", 1))
    ev = run(req(), ctx_full)
    assert of(ev, Citation)
    assert len(fake_brain.calls) == 2
    assert text.RETRY_PROMPT == ("Your quote was not found word for word. Copy a shorter exact "
                                 "sentence from the text, or answer null.")
    assert text.RETRY_PROMPT in fake_brain.calls[1]["messages"][-1]["content"]


def test_null_answer_refuses(fake_brain, ctx_full):
    fake_brain('{"answer":null,"quote":null,"page":null}')
    ev = run(req(), ctx_full)
    assert of(ev, Refusal)[0].reason == "not_in_document"
    assert len(fake_brain.calls) == 1
    assert ev[-1].answer == ""


def test_json_inside_prose(fake_brain, ctx_full):
    fake_brain('Here you go: {"answer":"Turn the front feet.","quote":"turn the front feet",'
               '"page":2} hope it helps')
    ev = run(req(), ctx_full)
    assert of(ev, Citation)[0].page == 2


def _fake_embed(monkeypatch):
    vocab: dict[str, int] = {}

    def fake_embed(texts):
        rows = np.zeros((len(texts), 64), dtype=np.float32)
        for r, t in enumerate(texts):
            for w in t.lower().split():
                rows[r, vocab.setdefault(w, len(vocab)) % 64] += 1
            rows[r] /= np.linalg.norm(rows[r]) or 1
        return rows

    monkeypatch.setattr(embeddings, "embed", fake_embed)


def test_long_doc_uses_rag(fake_brain, ctx_full, monkeypatch):
    _fake_embed(monkeypatch)
    pages = [" ".join(f"p{p}w{i}" for i in range(400)) for p in range(30)]
    pages[4] += " Clean the drain pump filter every month."
    fake_brain(reply("Clean it.", "Clean the drain pump filter every month", 5))
    ev = run(req("clean the drain pump filter", pages), ctx_full)
    stages = [e.stage for e in of(ev, Status)]
    assert stages[0] == "retrieving"
    prompt = fake_brain.calls[0]["messages"][-1]["content"]
    assert 0 < prompt.count("[page ") <= ctx_full.profile.text.rag_top_k <= 5
    # verified against full pages, not just chunks
    assert of(ev, Citation)[0].page == 5


def test_rag_verifies_against_full_pages(fake_brain, ctx_full, monkeypatch):
    _fake_embed(monkeypatch)
    pages = [" ".join(f"p{p}w{i}" for i in range(400)) for p in range(30)]
    pages[20] += " The secret hatch is behind the kick plate."
    fake_brain(reply("Behind the kick plate.", "The secret hatch is behind the kick plate", None))
    ev = run(req("where is the hatch", pages), ctx_full)
    assert of(ev, Citation)[0].page == 21


def test_manual_cache_reloads_after_replace(tmp_path, monkeypatch):
    monkeypatch.setattr(text, "MANUALS_DIR", tmp_path)
    path = tmp_path / "m1.pdf"

    def write(body):
        d = pymupdf.open()
        d.new_page().insert_text((72, 72), body)
        d.save(path)
        d.close()

    write("alpha text here")
    name, pages = text.load_manual("m1")
    assert name == "m1.pdf" and "alpha" in pages[0]
    write("bravo text here")
    st = path.stat()
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
    assert "bravo" in text.load_manual("m1")[1][0]


def test_manual_id_used_when_no_attachment(fake_brain, ctx_full, tmp_path, monkeypatch):
    monkeypatch.setattr(text, "MANUALS_DIR", tmp_path)
    d = pymupdf.open()
    d.new_page().insert_text((72, 72), "Turn the front feet to level the washer.")
    d.save(tmp_path / "w1.pdf")
    fake_brain(reply("Turn the front feet.", "Turn the front feet to level", 1))
    ev = run(PipelineRequest("level?", [], "manual_lookup", manual_id="w1"), ctx_full)
    c = of(ev, Citation)[0]
    assert c.source == "w1.pdf" and c.page == 1  # a 1-page PDF keeps its page


def test_missing_manual_refuses(fake_brain, ctx_full, tmp_path, monkeypatch):
    monkeypatch.setattr(text, "MANUALS_DIR", tmp_path)
    ev = run(PipelineRequest("q", [], "manual_lookup", manual_id="nope"), ctx_full)
    assert ev[-2] == Refusal(reason="no_document", message=MESSAGES["no_document"])
    assert ev[-1].answer == ""


def test_no_document_refuses(ctx_full):
    ev = run(PipelineRequest("q", [], "doc_qa"), ctx_full)
    assert of(ev, Refusal)[0].reason == "no_document"


def test_txt_single_page_citation_page_none(fake_brain, ctx_full):
    fake_brain(reply("Turn the feet.", "turn the front feet", 1))
    ev = run(req(pages=["To level it, turn the front feet."], name="notes.txt"), ctx_full)
    assert of(ev, Citation)[0].page is None


def test_ollama_down_refuses(monkeypatch, ctx_full):
    def boom(*a, **k):
        raise ModelUnavailable(MESSAGES["ollama_down"])

    monkeypatch.setattr(ollama_client, "chat", boom)
    ev = run(req(), ctx_full)
    r = of(ev, Refusal)[0]
    assert r.reason == "model_unavailable" and r.message == MESSAGES["ollama_down"]
    assert ev[-1].answer == ""


def test_timeout_refuses(monkeypatch, ctx_full):
    def boom(*a, **k):
        raise ModelTimeout(MESSAGES["timeout"])

    monkeypatch.setattr(ollama_client, "chat", boom)
    r = of(run(req(), ctx_full), Refusal)[0]
    assert r.reason == "timeout" and r.message == MESSAGES["timeout"]


@pytest.mark.parametrize("pages", [[], [""]])
def test_empty_document_refuses(pages, ctx_full):
    ev = run(req(pages=pages), ctx_full)
    assert of(ev, Refusal)[0].reason == "no_document"


@pytest.mark.parametrize("bad", ["../x", "/etc/passwd", "a/b", "..", "x\x00y"])
def test_manual_id_cannot_escape(bad, fake_brain, ctx_full, tmp_path, monkeypatch):
    monkeypatch.setattr(text, "MANUALS_DIR", tmp_path / "manuals")
    (tmp_path / "manuals").mkdir()
    fake_brain()
    ev = run(PipelineRequest("q", [], "manual_lookup", manual_id=bad), ctx_full)
    assert ev[-2] == Refusal(reason="no_document", message=MESSAGES["no_document"])
    assert isinstance(ev[-1], Final) and fake_brain.calls == []


def test_valid_manual_id_loads(fake_brain, ctx_full, tmp_path, monkeypatch):
    monkeypatch.setattr(text, "MANUALS_DIR", tmp_path)
    d = pymupdf.open()
    d.new_page().insert_text((72, 72), "Turn the front feet to level the washer.")
    d.save(tmp_path / "washer_lg-2.1.pdf")
    fake_brain(reply("Turn the front feet.", "Turn the front feet to level", 1))
    ev = run(PipelineRequest("level?", [], "manual_lookup", manual_id="washer_lg-2.1"), ctx_full)
    assert of(ev, Citation)


def test_question_code_missing_refuses_without_retry(fake_brain, ctx_full):
    pages = ["Error E21 means the water did not drain.", "The programme was not finished properly."]
    fake_brain(reply("The programme did not finish.", "The programme was not finished properly", 2))
    ev = run(req("What does error code E21 mean?", pages), ctx_full)
    assert of(ev, Refusal)[0].reason == "not_in_document"
    assert ev[-1].answer == "" and isinstance(ev[-1], Final)
    assert len(fake_brain.calls) == 1


def test_system_prompt_asks_for_short_answer(fake_brain, ctx_full):
    fake_brain(reply("Clean it.", "Clean the drain pump filter every month", 1))
    run(req(), ctx_full)
    assert "at most 2 sentences" in fake_brain.calls[0]["messages"][0]["content"]
