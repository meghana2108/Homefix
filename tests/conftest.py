import os
import types
from pathlib import Path

import pytest

from app.contracts import Ctx
from app.settings import load_profile


@pytest.fixture
def pack_dir() -> Path:
    raw = os.environ.get("PRACTICE_PACK_DIR")
    if not raw or not Path(raw).is_dir():
        pytest.skip("PRACTICE_PACK_DIR not set")
    return Path(raw)


@pytest.fixture
def profile_full():
    return load_profile("full")


@pytest.fixture
def profile_lite():
    return load_profile("lite")


@pytest.fixture
def ctx_full(profile_full):
    return Ctx(profile_full, memory=types.SimpleNamespace(), deadline_s=profile_full.server.model_call_timeout_s)


@pytest.fixture
def ctx_lite(profile_lite):
    return Ctx(profile_lite, memory=types.SimpleNamespace(), deadline_s=profile_lite.server.model_call_timeout_s)
