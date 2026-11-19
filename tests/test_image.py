import pytest

from app import prompts
from app.contracts import (
    MESSAGES,
    Attachment,
    Final,
    ModelUnavailable,
    PipelineRequest,
    Refusal,
    Token,
)
from app.models import ollama_client
from app.numbers import first_int
from app.pipelines import image, video
from tests.media_fixtures import make_jpeg


def req(tmp_path, message="How many mugs are on the shelf?", qtype="count", n=1, circles=3):
    atts = [Attachment(make_jpeg(tmp_path / f"i{k}.jpg", circles=circles), "image", f"i{k}.jpg") for k in range(n)]
    return PipelineRequest(message, atts, qtype)


def test_count_number_first(ctx_full, fake_brain, tmp_path):
    fake_brain("four mugs on the shelf")
    ev = list(image.run(req(tmp_path), ctx_full))
    assert isinstance(ev[-1], Final)
    assert ev[-1].answer == "4. four mugs on the shelf"
    assert ev[-1].model == ctx_full.profile.models.brain


def test_count_cant_tell_kept(ctx_full, fake_brain, tmp_path):
    fake_brain("I can't tell.")
    ev = list(image.run(req(tmp_path), ctx_full))
    assert ev[-1].answer == "I can't tell."


def test_count_prompt_names_thing(ctx_full, fake_brain, tmp_path):
    fake_brain("3 mugs.")
    list(image.run(req(tmp_path), ctx_full))
    assert "Count the mugs" in fake_brain.calls[0]["messages"][-1]["content"]


def test_images_sent(ctx_full, fake_brain, tmp_path):
    fake_brain("A desk.")
    list(image.run(req(tmp_path, "", "describe", n=2), ctx_full))
    assert len(fake_brain.calls[0]["images"]) == 2


def test_tokens_streamed(ctx_full, fake_brain, tmp_path):
    fake_brain("A tidy desk with a lamp.")
    ev = list(image.run(req(tmp_path, "", "describe"), ctx_full))
    idx = [i for i, e in enumerate(ev) if isinstance(e, Token)]
    assert len(idx) >= 2 and idx[-1] < len(ev) - 1


def test_tokens_stream_live(ctx_full, tmp_path, monkeypatch):
    """The first token must reach the UI while the brain is still generating."""
    progress = {"done": False}

    def slow_brain(*a, **kw):
        yield "The "
        yield "desk "
        progress["done"] = True
        yield "is tidy."
    monkeypatch.setattr(ollama_client, "chat_stream", slow_brain)
    for ev in image.run(req(tmp_path, "", "describe"), ctx_full):
        if isinstance(ev, Token):
            assert progress["done"] is False
            break
    else:
        pytest.fail("no token")


def test_refusal_then_empty_final(ctx_full, tmp_path, monkeypatch):
    def down(*a, **kw):
        raise ModelUnavailable(MESSAGES["ollama_down"])
        yield
    monkeypatch.setattr(ollama_client, "chat_stream", down)
    ev = list(image.run(req(tmp_path), ctx_full))
    assert isinstance(ev[-2], Refusal)
    assert isinstance(ev[-1], Final) and ev[-1].answer == ""
    assert sum(isinstance(e, Final) for e in ev) == 1


def test_read_and_describe_prompts(ctx_full, fake_brain, tmp_path):
    fake_brain("EXIT", "A room.")
    list(image.run(req(tmp_path, "what does it say", "read"), ctx_full))
    list(image.run(req(tmp_path, "", "describe"), ctx_full))
    assert fake_brain.calls[0]["messages"][-1]["content"] == prompts.READ_PROMPT
    assert fake_brain.calls[1]["messages"][-1]["content"] == prompts.DESCRIBE_PROMPT


@pytest.mark.parametrize("text", ["How many mugs are on the shelf?", "four mugs", "I can't tell.",
                                  "12 cups, maybe 13", ""])
def test_matches_video_copies(text):
    assert prompts.count_prompt(text) == video.count_prompt(text)
    assert prompts.force_number_first(text) == video.force_number_first(text)
    assert first_int(text) == video.first_int(text)
    assert prompts.READ_PROMPT == video.READ_PROMPT


@pytest.mark.model
def test_real_count(ctx_full, tmp_path):
    ev = list(image.run(req(tmp_path, "How many red circles are there?"), ctx_full))
    print(ev[-1].answer)
    assert first_int(ev[-1].answer) == 3
