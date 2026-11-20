"""Ready before anyone asks: every model loads at API start, the app shows "Getting ready" until then, and after a
code answer the vision model comes straight back (one big model at a time), so the next photo question isn't cold."""

import threading

import pytest
from fastapi.testclient import TestClient

from app import warmup
from app.api.main import app


@pytest.fixture
def steps(monkeypatch):
    calls = []

    def make(name, fail=False):
        def fn(ctx):
            calls.append(name)
            if fail:
                raise RuntimeError("not cached")
        return fn
    monkeypatch.setattr(warmup, "steps", lambda ctx: [("brain", "Vision model", make("brain")),
                                                       ("whisper", "Speech", make("whisper", fail=True)),
                                                       ("clap", "Sounds", make("clap"))])
    warmup.reset()
    return calls


def test_warmup_loads_each_model_and_reports_each_step(ctx_full, steps):
    warmup.run(ctx_full)
    assert steps == ["brain", "whisper", "clap"]
    st = warmup.status()
    assert [s["name"] for s in st["steps"]] == ["brain", "whisper", "clap"]
    assert [s["state"] for s in st["steps"]] == ["ready", "failed", "ready"]
    assert st["ready"] is False and st["done"] is True  # a failed step: done, but not all ready
    assert all(isinstance(s["ms"], int) for s in st["steps"])


def test_all_ready(ctx_full, monkeypatch):
    monkeypatch.setattr(warmup, "steps", lambda ctx: [("brain", "Vision model", lambda c: None)])
    warmup.reset()
    warmup.run(ctx_full)
    assert warmup.status() == {"ready": True, "done": True, "steps": [
        {"name": "brain", "label": "Vision model", "state": "ready", "ms": warmup.status()["steps"][0]["ms"]}]}


def test_before_it_runs_everything_is_waiting(ctx_full, steps):
    st = warmup.status()
    assert st["ready"] is False and st["done"] is False


def test_the_steps_are_listed_the_moment_it_starts(ctx_full, monkeypatch):
    """Found in the browser: in the first instant the step list was empty and the app took that for "ready"."""
    gate = threading.Event()
    monkeypatch.setattr(warmup, "steps", lambda ctx: [("brain", "Vision model", lambda c: gate.wait(5))])
    monkeypatch.setenv("HOMEFIX_WARMUP", "on")
    warmup.reset()
    t = warmup.start(ctx_full)
    st = warmup.status()
    gate.set()
    t.join(5)
    assert st["done"] is False and [s["name"] for s in st["steps"]] == ["brain"]


def test_warmup_is_off_in_tests_and_can_be_turned_off(ctx_full, steps, monkeypatch):
    monkeypatch.setenv("HOMEFIX_WARMUP", "off")
    assert warmup.start(ctx_full) is None
    assert steps == []


def test_health_says_whether_homefix_is_ready(ctx_full, steps):
    app.state.ctx = ctx_full
    try:
        warmup.run(ctx_full)
        body = TestClient(app).get("/api/health").json()
    finally:
        del app.state.ctx
    assert body["warm"]["done"] is True and len(body["warm"]["steps"]) == 3


def test_the_real_steps_cover_every_resident_model(ctx_full):
    names = [n for n, _, _ in warmup.steps(ctx_full)]
    assert names == ["brain", "whisper_file", "whisper_live", "clap", "embeddings"]


def test_after_a_code_answer_the_vision_model_comes_back(ctx_full, fake_backend, monkeypatch):
    """full swaps the coder in with the brain out; the next photo question used to reload the brain itself."""
    from app import orchestrate
    ctx_full.memory.backend = fake_backend
    fake_backend.loaded_tags = [ctx_full.profile.models.coder]
    done = threading.Event()
    orig = ctx_full.memory.restore

    def restore(role):
        orig(role).join(5)
        done.set()
    monkeypatch.setattr(ctx_full.memory, "restore", restore)
    monkeypatch.setattr("app.pipelines.code.run", lambda req, ctx: iter(()))
    list(orchestrate.handle("Write a function that adds two numbers.", [], None, ctx_full))
    assert done.wait(5)
    assert fake_backend.loaded_tags == [ctx_full.profile.models.brain]
    assert ctx_full.profile.models.coder in fake_backend.unload_calls
