import os
import re
from pathlib import Path

import pytest

from app.contracts import MESSAGES, Ctx, ModelUnavailable
from app.models.memory import MemoryManager
from app.settings import load_profile

# The API warms every model at startup (app/warmup.py). Tests never load real models that way.
os.environ.setdefault("HOMEFIX_WARMUP", "off")


@pytest.fixture
def pack_dir() -> Path:
    raw = os.environ.get("PRACTICE_PACK_DIR")
    if not raw or not Path(raw).is_dir():
        pytest.skip("PRACTICE_PACK_DIR not set")
    return Path(raw)


@pytest.fixture(autouse=True)
def _no_meaning_net_by_default(request, monkeypatch):
    """The meaning-based danger net loads an embedding model (~9 s). Unit tests get a neutral score unless they
    ask for the real one (tests marked `model`) or set their own scores (tests/test_safety_semantic.py)."""
    if request.node.get_closest_marker("model"):
        return
    from app import intent, safety_semantic
    monkeypatch.setattr(safety_semantic, "scores", lambda text: (0.0, 0.0, "none"))
    monkeypatch.setattr(intent, "lean", lambda text, side, other: -1.0)  # word rules only


@pytest.fixture
def profile_full():
    return load_profile("full")


@pytest.fixture
def profile_lite():
    return load_profile("lite")


class FakeBackend:
    """In-memory stand-in for OllamaBackend. Tests set loaded_tags and read the call lists."""

    def __init__(self):
        self.loaded_tags: list[str] = []
        self.load_calls: list[tuple[str, int, int | None]] = []
        self.unload_calls: list[str] = []
        self.fail_load = False

    def loaded(self) -> list[str]:
        return list(self.loaded_tags)

    def load(self, tag: str, keep_alive: int, num_ctx: int | None = None) -> None:
        if self.fail_load:
            raise ModelUnavailable(MESSAGES["ollama_down"])
        self.load_calls.append((tag, keep_alive, num_ctx))
        if tag not in self.loaded_tags:
            self.loaded_tags.append(tag)

    def unload(self, tag: str) -> None:
        self.unload_calls.append(tag)
        self.loaded_tags = [t for t in self.loaded_tags if t != tag]


@pytest.fixture
def fake_backend() -> FakeBackend:
    return FakeBackend()


@pytest.fixture
def ctx_full(profile_full, fake_backend):
    """full as it runs on the M4: brain and coder already resident."""
    fake_backend.loaded_tags = [profile_full.models.brain, profile_full.models.coder]
    return Ctx(profile_full, memory=MemoryManager(profile_full, fake_backend),
               deadline_s=profile_full.server.model_call_timeout_s)


@pytest.fixture
def ctx_lite(profile_lite, fake_backend):
    """lite as it runs on the M2: only the brain resident."""
    fake_backend.loaded_tags = [profile_lite.models.brain]
    return Ctx(profile_lite, memory=MemoryManager(profile_lite, fake_backend),
               deadline_s=profile_lite.server.model_call_timeout_s)


class FakeBrain:
    """fake_brain(*replies): each chat / chat_stream call returns the next reply.

    chat_stream yields the reply split into words (spaces kept). Every call's arguments are
    recorded in fake_brain.calls as a dict (model, messages, images, num_ctx, keep_alive, timeout_s,
    json_format, temperature, seed). Running out of replies fails the test.
    """

    def __init__(self, monkeypatch):
        self._monkeypatch = monkeypatch
        self.replies: list[str] = []
        self.calls: list[dict] = []

    def _next(self) -> str:
        if not self.replies:
            raise AssertionError("fake_brain ran out of replies (a model was called unexpectedly)")
        return self.replies.pop(0)

    def __call__(self, *replies: str) -> "FakeBrain":
        from app.models import ollama_client

        self.replies = list(replies)
        self.calls.clear()

        def chat_stream(model, messages, images=None, *, num_ctx, keep_alive, timeout_s):
            self.calls.append({"model": model, "messages": messages, "images": images, "num_ctx": num_ctx,
                               "keep_alive": keep_alive, "timeout_s": timeout_s})
            yield from re.findall(r"\S+\s*|\s+", self._next())

        def chat(model, messages, *, num_ctx, keep_alive, timeout_s, json_format=False,
                 temperature=None, seed=None):
            self.calls.append({"model": model, "messages": messages, "images": None, "num_ctx": num_ctx,
                               "keep_alive": keep_alive, "timeout_s": timeout_s, "json_format": json_format,
                               "temperature": temperature, "seed": seed})
            return self._next()

        self._monkeypatch.setattr(ollama_client, "chat_stream", chat_stream)
        self._monkeypatch.setattr(ollama_client, "chat", chat)
        return self


@pytest.fixture
def fake_brain(monkeypatch) -> FakeBrain:
    return FakeBrain(monkeypatch)
