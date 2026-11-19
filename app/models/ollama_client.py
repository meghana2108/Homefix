"""The one place that talks to Ollama.

Call these as module attributes (ollama_client.chat_stream) so tests can monkeypatch them.
Server down -> ModelUnavailable(MESSAGES["ollama_down"]); model not pulled ->
ModelUnavailable(MESSAGES["model_missing"]); too slow -> ModelTimeout(MESSAGES["timeout"]).
Every call passes think=False and retries without it if the model rejects the flag (D7).
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import httpx
import ollama

from app.contracts import MESSAGES, ModelTimeout, ModelUnavailable
from app.settings import load_env


def _client(timeout_s: float) -> ollama.Client:
    return ollama.Client(host=load_env().ollama_host, timeout=timeout_s)


def _translate(e: Exception, model: str) -> Exception:
    """Map a library error to our contract errors; anything else is returned unchanged."""
    if isinstance(e, (ModelUnavailable, ModelTimeout)):
        return e
    if isinstance(e, httpx.TimeoutException):
        return ModelTimeout(MESSAGES["timeout"])
    if isinstance(e, (ConnectionError, httpx.ConnectError, httpx.RemoteProtocolError)):
        return ModelUnavailable(MESSAGES["ollama_down"])
    if isinstance(e, ollama.ResponseError) and (e.status_code == 404 or "not found" in str(e).lower()):
        return ModelUnavailable(MESSAGES["model_missing"].format(role=model))
    return e


def _with_images(messages: list[dict], images: list[Path] | None) -> list[dict]:
    """Copy messages; attach image paths to the last user message."""
    out = [dict(m) for m in messages]
    if images:
        for m in reversed(out):
            if m.get("role") == "user":
                m["images"] = [str(p) for p in images]
                break
    return out


def _call(client: ollama.Client, kwargs: dict[str, Any]) -> Any:
    try:
        return client.chat(think=False, **kwargs)
    except ollama.ResponseError as e:
        if "think" not in str(e).lower():
            raise
        return client.chat(**kwargs)


def _guarded(model: str, fn: Callable[[], Any]) -> Any:
    try:
        return fn()
    except Exception as e:
        raise _translate(e, model) from e


def chat_stream(model: str, messages: list[dict], images: list[Path] | None = None, *,
                num_ctx: int, keep_alive: int, timeout_s: float) -> Iterator[str]:
    """Yield the answer text chunk by chunk. Stops with ModelTimeout once timeout_s has passed
    in total (httpx's own timeout is per read, so a slow trickle would never trip it)."""
    deadline = time.monotonic() + timeout_s
    kwargs = {"model": model, "messages": _with_images(messages, images), "stream": True,
              "keep_alive": keep_alive, "options": {"num_ctx": num_ctx}}
    stream = _guarded(model, lambda: _call(_client(timeout_s), kwargs))
    it, end = iter(stream), object()
    while True:
        part = _guarded(model, lambda: next(it, end))
        if part is end:
            return
        if time.monotonic() > deadline:
            raise ModelTimeout(MESSAGES["timeout"])
        text = part.message.content or ""
        if text:
            yield text


def chat(model: str, messages: list[dict], *, num_ctx: int, keep_alive: int, timeout_s: float,
         json_format: bool = False, temperature: float | None = None,
         seed: int | None = None) -> str:
    """One complete answer. json_format=True asks Ollama for JSON output.
    temperature and seed (when set) make the answer repeatable."""
    kwargs: dict[str, Any] = {"model": model, "messages": _with_images(messages, None),
                              "keep_alive": keep_alive, "options": {"num_ctx": num_ctx}}
    if temperature is not None:
        kwargs["options"]["temperature"] = temperature
    if seed is not None:
        kwargs["options"]["seed"] = seed
    if json_format:
        kwargs["format"] = "json"
    r = _guarded(model, lambda: _call(_client(timeout_s), kwargs))
    return r.message.content or ""


def is_up() -> bool:
    """GET /api/version answers within 1 s."""
    try:
        r = httpx.get(f"{load_env().ollama_host}/api/version", timeout=1.0)
        return r.status_code == 200
    except (httpx.HTTPError, ValueError):
        return False


class OllamaBackend:
    """What MemoryManager drives: list, load and unload models in the Ollama server."""

    def __init__(self, timeout_s: float = 120.0):
        self.timeout_s = timeout_s

    def loaded(self) -> list[str]:
        r = _guarded("ollama", lambda: _client(5).ps())
        return [m.model for m in r.models]

    def load(self, tag: str, keep_alive: int, num_ctx: int | None = None) -> None:
        """An empty generate loads the model. Pass the same num_ctx the calls will use:
        Ollama reloads a model whose num_ctx changes."""
        kw: dict[str, Any] = {"model": tag, "prompt": "", "keep_alive": keep_alive}
        if num_ctx:
            kw["options"] = {"num_ctx": num_ctx}
        _guarded(tag, lambda: _client(self.timeout_s).generate(**kw))

    def unload(self, tag: str) -> None:
        _guarded(tag, lambda: _client(30).generate(model=tag, prompt="", keep_alive=0))
