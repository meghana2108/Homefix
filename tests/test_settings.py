import os

import pytest

import app.settings  # noqa: F401
from app.settings import load_env, load_profile


def test_offline_env_set():
    assert os.environ["HF_HUB_OFFLINE"] == "1"
    assert os.environ["TRANSFORMERS_OFFLINE"] == "1"


def test_profiles_load():
    assert load_profile("full").video.frames == 16
    assert load_profile("lite").video.frames == 8
    assert load_profile("lite").audio.alarm_safety_min_score == 0.5
    assert load_profile("full").server.max_file_mb == 200


def test_unknown_profile():
    with pytest.raises(ValueError, match="Unknown profile 'big'"):
        load_profile("big")


def test_remote_ollama_rejected(monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "http://10.0.0.5:11434")
    with pytest.raises(ValueError, match="no network at runtime"):
        load_env()
