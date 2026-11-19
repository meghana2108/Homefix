"""Ollama client: down / missing / slow become clear errors; think=False with a fallback."""

import time
from types import SimpleNamespace

import httpx
import ollama
import pytest

from app.contracts import MESSAGES, ModelTimeout, ModelUnavailable
from app.models import ollama_client
from app.models.ollama_client import OllamaBackend, chat, chat_stream, is_up

DOWN = "http://127.0.0.1:9"


def _msg(content="", thinking=None):
    return SimpleNamespace(message=SimpleNamespace(content=content, thinking=thinking))


class FakeClient:
    """Stands in for ollama.Client; records every chat call."""

    def __init__(self, *, chunks=(), reply="", raise_on_think=False, error=None, delay=0.0):
        self.chunks, self.reply, self.raise_on_think = list(chunks), reply, raise_on_think
        self.error, self.delay, self.calls = error, delay, []

    def chat(self, **kw):
        self.calls.append(kw)
        if self.raise_on_think and "think" in kw:
            raise ollama.ResponseError('"x" does not support thinking', 400)
        if self.error:
            raise self.error
        if kw.get("stream"):
            def gen():
                for c in self.chunks:
                    time.sleep(self.delay)
                    yield _msg(c)
            return gen()
        return _msg(self.reply)


@pytest.fixture
def fake_client(monkeypatch):
    def install(**kw):
        client = FakeClient(**kw)
        monkeypatch.setattr(ollama_client, "_client", lambda timeout_s: client)
        return client
    return install


KW = {"num_ctx": 512, "keep_alive": 0, "timeout_s": 2}


def test_down_is_model_unavailable(monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", DOWN)
    t0 = time.time()
    with pytest.raises(ModelUnavailable) as e:
        list(chat_stream("x", [], **KW))
    assert str(e.value) == "The local model server isn't running. Start Ollama and try again."
    assert time.time() - t0 < 3


def test_down_non_streaming(monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", DOWN)
    with pytest.raises(ModelUnavailable, match="isn't running"):
        chat("x", [], **KW)


def test_is_up_false_when_down(monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", DOWN)
    assert is_up() is False


def test_missing_model(fake_client):
    fake_client(error=ollama.ResponseError("model 'qwen9:1b' not found", 404))
    with pytest.raises(ModelUnavailable) as e:
        list(chat_stream("qwen9:1b", [], **KW))
    assert str(e.value) == MESSAGES["model_missing"].format(role="qwen9:1b")


def test_read_timeout_is_model_timeout(fake_client):
    fake_client(error=httpx.ReadTimeout("slow"))
    with pytest.raises(ModelTimeout) as e:
        chat("x", [], **KW)
    assert str(e.value) == MESSAGES["timeout"]


def test_stream_over_deadline_is_timeout(fake_client):
    """httpx times out per read; a stream that keeps trickling must still stop at timeout_s."""
    fake_client(chunks=["a"] * 50, delay=0.05)
    with pytest.raises(ModelTimeout):
        list(chat_stream("x", [], num_ctx=512, keep_alive=0, timeout_s=0.5))


def test_think_false_and_options(fake_client, tmp_path):
    client = fake_client(chunks=["There ", "are ", "", "4."])
    img = tmp_path / "a.jpg"
    img.write_bytes(b"x")
    out = list(chat_stream("m", [{"role": "system", "content": "s"}, {"role": "user", "content": "q"}], [img],
                           num_ctx=8192, keep_alive=-1, timeout_s=5))
    assert out == ["There ", "are ", "4."]  # empty chunks dropped
    call = client.calls[0]
    assert call["think"] is False and call["stream"] is True
    assert call["options"]["num_ctx"] == 8192 and call["keep_alive"] == -1
    assert call["messages"][-1]["images"] == [str(img)]
    assert "images" not in call["messages"][0]


def test_images_go_on_last_user_message_without_mutating(fake_client, tmp_path):
    client = fake_client(chunks=["ok"])
    msgs = [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}]
    list(chat_stream("m", msgs, [tmp_path / "x.jpg"], **KW))
    assert client.calls[0]["messages"][0]["images"] == [str(tmp_path / "x.jpg")]
    assert "images" not in msgs[0]


def test_retries_without_think(fake_client):
    client = fake_client(reply='{"a": 1}', raise_on_think=True)
    assert chat("m", [], json_format=True, **KW) == '{"a": 1}'
    assert len(client.calls) == 2 and "think" not in client.calls[1]
    assert client.calls[1]["format"] == "json"


def test_backend_load_and_unload(monkeypatch):
    calls = []
    client = SimpleNamespace(
        generate=lambda **kw: calls.append(kw),
        ps=lambda: SimpleNamespace(models=[SimpleNamespace(model="qwen3-vl:2b-instruct", size=2.7e9)]),
    )
    monkeypatch.setattr(ollama_client, "_client", lambda timeout_s: client)
    b = OllamaBackend()
    b.load("m:1b", keep_alive=-1, num_ctx=8192)
    b.unload("m:1b")
    assert calls[0] == {"model": "m:1b", "prompt": "", "keep_alive": -1, "options": {"num_ctx": 8192}}
    assert calls[1] == {"model": "m:1b", "prompt": "", "keep_alive": 0}
    assert b.loaded() == ["qwen3-vl:2b-instruct"]


@pytest.mark.model
def test_real_stream(profile_lite):
    out = "".join(chat_stream(profile_lite.models.brain, [{"role": "user", "content": "Reply with the word ok."}],
                              num_ctx=profile_lite.brain_num_ctx, keep_alive=-1, timeout_s=60))
    assert "ok" in out.lower()


@pytest.mark.model
def test_brain_does_not_think_with_an_image(profile_lite, tmp_path):
    """qwen3-vl:2b (the thinking build) thinks even with think=False when an image is attached."""
    from PIL import Image

    img = tmp_path / "a.jpg"
    Image.new("RGB", (64, 64), "red").save(img)
    c = ollama_client._client(60)
    r = c.chat(model=profile_lite.models.brain, think=False, keep_alive=-1,
               messages=[{"role": "user", "content": "What colour is this? One word.", "images": [str(img)]}],
               options={"num_ctx": profile_lite.brain_num_ctx, "num_predict": 20})
    assert not (r.message.thinking or "").strip()
    assert "red" in r.message.content.lower()
