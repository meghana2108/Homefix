"""Memory manager: lite keeps one LLM loaded and reports the swap time; full keeps both."""

import time

from app.contracts import Status
from app.models.memory import MemoryManager, measure_gb


def test_lite_swaps_one_llm(profile_lite, fake_backend):
    fake_backend.loaded_tags = [profile_lite.models.brain]
    events = list(MemoryManager(profile_lite, fake_backend).ensure("coder"))
    assert len(events) == 1
    ev = events[0]
    assert isinstance(ev, Status) and ev.stage == "loading_model"
    assert isinstance(ev.ms, int) and ev.ms >= 0
    assert ev.detail == "loading qwen2.5-coder:3b"
    assert fake_backend.loaded_tags == ["qwen2.5-coder:3b"]


def test_lite_back_to_brain(profile_lite, fake_backend):
    fake_backend.loaded_tags = [profile_lite.models.brain]
    mm = MemoryManager(profile_lite, fake_backend)
    list(mm.ensure("coder"))
    events = list(mm.ensure("brain"))
    assert [e.stage for e in events] == ["loading_model"]
    assert fake_backend.loaded_tags == [profile_lite.models.brain]  # never both


def test_lite_unloads_anything_else(profile_lite, fake_backend):
    """An old tag left over in Ollama (e.g. the thinking build) is also unloaded on lite."""
    fake_backend.loaded_tags = ["qwen3-vl:2b", profile_lite.models.brain]
    list(MemoryManager(profile_lite, fake_backend).ensure("brain"))
    assert fake_backend.loaded_tags == [profile_lite.models.brain]


def test_lite_already_loaded_is_silent(profile_lite, fake_backend):
    fake_backend.loaded_tags = [profile_lite.models.brain]
    assert list(MemoryManager(profile_lite, fake_backend).ensure("brain")) == []
    assert fake_backend.load_calls == []


def test_full_keeps_both(profile_full, fake_backend):
    fake_backend.loaded_tags = [profile_full.models.brain, profile_full.models.coder]
    assert list(MemoryManager(profile_full, fake_backend).ensure("coder")) == []
    assert fake_backend.unload_calls == []


def test_full_loads_missing_without_unloading(profile_full, fake_backend):
    fake_backend.loaded_tags = [profile_full.models.brain]
    events = list(MemoryManager(profile_full, fake_backend).ensure("coder"))
    assert [e.stage for e in events] == ["loading_model"]
    assert sorted(fake_backend.loaded_tags) == sorted([profile_full.models.brain, profile_full.models.coder])


def test_loads_with_profile_num_ctx_and_keep_alive(profile_lite, fake_backend):
    """Ollama reloads a model when num_ctx changes, so the load must use the same num_ctx as the calls."""
    mm = MemoryManager(profile_lite, fake_backend)
    list(mm.ensure("coder"))
    assert fake_backend.load_calls == [("qwen2.5-coder:3b", 120, profile_lite.brain_num_ctx)]
    assert mm.num_ctx("coder") == mm.num_ctx("brain") == profile_lite.brain_num_ctx


def test_tag(profile_lite, fake_backend):
    mm = MemoryManager(profile_lite, fake_backend)
    assert mm.tag("brain") == profile_lite.models.brain and mm.tag("coder") == "qwen2.5-coder:3b"


def test_prefetch_noop_on_lite(profile_lite, fake_backend):
    MemoryManager(profile_lite, fake_backend).prefetch("coder")
    time.sleep(0.05)
    assert fake_backend.load_calls == []


def test_prefetch_loads_on_full_in_background(profile_full, fake_backend):
    fake_backend.loaded_tags = [profile_full.models.brain]
    MemoryManager(profile_full, fake_backend).prefetch("coder")
    for _ in range(100):
        if profile_full.models.coder in fake_backend.loaded_tags:
            break
        time.sleep(0.01)
    assert profile_full.models.coder in fake_backend.loaded_tags


def test_prefetch_swallows_errors(profile_full, fake_backend):
    fake_backend.fail_load = True
    MemoryManager(profile_full, fake_backend).prefetch("coder")  # must not raise in the caller
    time.sleep(0.05)


def test_measure_gb_never_raises(monkeypatch):
    from app.models import ollama_client

    def boom(timeout_s):
        raise ConnectionError("down")
    monkeypatch.setattr(ollama_client, "_client", boom)
    assert measure_gb() > 0  # this process's RSS alone
