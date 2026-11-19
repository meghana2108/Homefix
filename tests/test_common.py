"""stream_brain: tokens, plus clear refusals when the model is down or slow. Never raises."""

from app.contracts import MESSAGES, ModelTimeout, ModelUnavailable, Refusal, Status, Token
from app.models import ollama_client
from app.pipelines.common import collect, refused, stream_brain

MSGS = [{"role": "user", "content": "How many mugs?"}]


def test_stream_brain_tokens(ctx_full, fake_brain):
    fake_brain("There are 4 mugs.")
    events = list(stream_brain(ctx_full, MSGS))
    gen = [e for e in events if isinstance(e, Status) and e.stage == "generating"]
    assert gen and gen[0].detail == ctx_full.profile.models.brain
    tokens = [e for e in events if isinstance(e, Token)]
    assert len(tokens) >= 2 and "".join(t.text for t in tokens) == "There are 4 mugs."


def test_stream_brain_passes_images_and_ctx(ctx_lite, fake_brain, tmp_path):
    fake_brain("ok")
    img = tmp_path / "a.jpg"
    list(stream_brain(ctx_lite, MSGS, [img]))
    call = fake_brain.calls[0]
    assert call["images"] == [img] and call["model"] == ctx_lite.profile.models.brain
    assert call["num_ctx"] == ctx_lite.profile.brain_num_ctx
    assert call["timeout_s"] == ctx_lite.deadline_s


def test_stream_brain_lite_swap_first(ctx_lite, fake_backend, fake_brain):
    fake_backend.loaded_tags = ["qwen2.5-coder:3b"]
    fake_brain("ok")
    events = list(stream_brain(ctx_lite, MSGS))
    assert events[0].stage == "loading_model"
    assert fake_backend.loaded_tags == [ctx_lite.profile.models.brain]


def test_stream_brain_down_refuses(ctx_full, monkeypatch):
    def down(*a, **kw):
        raise ModelUnavailable(MESSAGES["ollama_down"])
        yield  # pragma: no cover
    monkeypatch.setattr(ollama_client, "chat_stream", down)
    events = list(stream_brain(ctx_full, MSGS))
    assert events[-1] == Refusal(reason="model_unavailable", message=MESSAGES["ollama_down"])


def test_stream_brain_load_failure_refuses(ctx_lite, fake_backend, fake_brain):
    fake_backend.loaded_tags = []
    fake_backend.fail_load = True
    fake_brain("never")
    events = list(stream_brain(ctx_lite, MSGS))
    assert events[-1].type == "refusal" and events[-1].reason == "model_unavailable"
    assert fake_brain.calls == []


def test_stream_brain_timeout_refuses(ctx_full, monkeypatch):
    def slow(*a, **kw):
        yield "partial "
        raise ModelTimeout(MESSAGES["timeout"])
    monkeypatch.setattr(ollama_client, "chat_stream", slow)
    events = list(stream_brain(ctx_full, MSGS))
    assert events[-1] == Refusal(reason="timeout",
                                 message="The model took too long. Try a shorter clip or a smaller question.")


def test_collect_and_refused(ctx_full, fake_brain):
    fake_brain("4 mugs")
    sink: list[str] = []
    seen = list(collect(stream_brain(ctx_full, MSGS), sink))
    assert "".join(sink) == "4 mugs" and not refused(seen)
    assert refused([Refusal(reason="timeout", message="x")])


def test_fake_brain_chat_and_calls(fake_brain):
    fake_brain('{"answer": "a"}', "second")
    assert ollama_client.chat("m", MSGS, num_ctx=1, keep_alive=0, timeout_s=1) == '{"answer": "a"}'
    assert "".join(ollama_client.chat_stream("m", MSGS, num_ctx=1, keep_alive=0, timeout_s=1)) == "second"
    assert [c["messages"] for c in fake_brain.calls] == [MSGS, MSGS]
