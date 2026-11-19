"""Which LLM is loaded in Ollama.

full: brain and coder both stay loaded; ensure() only loads what is missing.
lite: one LLM at a time. ensure() unloads everything else first, loads the target and reports
      the swap as Status(stage="loading_model", detail="loading <tag>", ms=<elapsed>).
Models are loaded with the same num_ctx the pipelines call them with (num_ctx()), because
Ollama reloads a model whose num_ctx changes.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from typing import Literal, Protocol

import psutil

from app.contracts import Status
from app.settings import Profile

Role = Literal["brain", "coder"]


class Backend(Protocol):
    def loaded(self) -> list[str]: ...
    def load(self, tag: str, keep_alive: int, num_ctx: int | None = None) -> None: ...
    def unload(self, tag: str) -> None: ...


class MemoryManager:
    def __init__(self, profile: Profile, backend: Backend):
        self.profile = profile
        self.backend = backend
        self._lock = threading.Lock()

    def tag(self, role: str) -> str:
        return getattr(self.profile.models, role)

    def keep_alive(self, role: Role) -> int:
        return getattr(self.profile.keep_alive, role)

    def num_ctx(self, role: Role) -> int:
        """The num_ctx every call to this role must use (and that it is loaded with)."""
        return self.profile.brain_num_ctx

    def _one_at_a_time(self) -> bool:
        return self.profile.name == "lite"

    def ensure(self, role: Role) -> Iterator[Status]:
        """Make `role` loaded. Yields one loading_model status when a load happened.
        Raises ModelUnavailable when Ollama is down or the model isn't pulled."""
        tag = self.tag(role)
        with self._lock:
            loaded = self.backend.loaded()
            others = [t for t in loaded if t != tag] if self._one_at_a_time() else []
            if tag in loaded and not others:
                return
            t0 = time.perf_counter()
            for other in others:
                self.backend.unload(other)
            if tag not in loaded:
                self.backend.load(tag, self.keep_alive(role), self.num_ctx(role))
            ms = int((time.perf_counter() - t0) * 1000)
        yield Status(stage="loading_model", detail=f"loading {tag}", ms=ms)

    def prefetch(self, role: Literal["coder"]) -> None:
        """full only: start loading in a background thread so the code answer starts sooner."""
        if self._one_at_a_time():
            return

        def work() -> None:
            try:
                for _ in self.ensure(role):
                    pass
            except Exception:  # noqa: BLE001, S110 - best effort; the real call reports errors
                pass

        threading.Thread(target=work, name=f"prefetch-{role}", daemon=True).start()


def measure_gb() -> float:
    """Ollama's loaded model sizes plus this process's RSS, in GB. Never raises."""
    from app.models import ollama_client

    total = psutil.Process().memory_info().rss
    try:
        total += sum(m.size for m in ollama_client._client(2).ps().models)
    except Exception:  # noqa: BLE001, S110 - diagnostics only
        pass
    return total / 1e9
