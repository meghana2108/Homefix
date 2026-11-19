"""Profile and environment loading. Importing this module turns on offline mode."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

import yaml
from pydantic import BaseModel, ConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.contracts import ProfileName

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

ROOT = Path(__file__).resolve().parents[1]
MANUALS_DIR = ROOT / "data/manuals"
SOUND_LABEL_FILES: tuple[Path, Path] = (
    ROOT / "config/sound_labels/general.txt",
    ROOT / "config/sound_labels/appliances.txt",
)


class Env(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    profile: ProfileName = "full"
    ollama_host: str = "http://127.0.0.1:11434"
    practice_pack_dir: Path | None = None


def load_env() -> Env:
    env = Env()
    if urlparse(env.ollama_host).hostname not in ("127.0.0.1", "localhost"):
        raise ValueError("OLLAMA_HOST must be localhost or 127.0.0.1 (no network at runtime).")
    return env


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Models(_Strict):
    brain: str
    coder: str
    whisper_file: str
    whisper_live: str
    clap: str
    embeddings: str


class KeepAlive(_Strict):
    brain: int
    coder: int


class ImageCfg(_Strict):
    max_side: int


class VideoCfg(_Strict):
    frames: int
    frame_side: int
    read_extra_frames: int


class TextCfg(_Strict):
    full_doc_max_tokens: int
    rag_top_k: int
    quote_fuzz_threshold: int


class CodeCfg(_Strict):
    selfcheck_timeout_s: int
    max_retries: int


class AudioCfg(_Strict):
    speech_max_no_speech_prob: float
    alarm_safety_min_score: float
    top_k: int


class ServerCfg(_Strict):
    max_files: int
    max_file_mb: int
    video_max_seconds: int
    model_call_timeout_s: int


class Profile(_Strict):
    name: ProfileName
    models: Models
    resident: list[str]
    swap: list[str] = []
    keep_alive: KeepAlive
    image: ImageCfg
    video: VideoCfg
    text: TextCfg
    brain_num_ctx: int
    code: CodeCfg
    audio: AudioCfg
    server: ServerCfg
    cache_dir: str


def load_profile(name: str | None = None) -> Profile:
    if name is None:
        name = load_env().profile
    path = ROOT / "config" / "profiles" / f"{name}.yaml"
    if name not in ("full", "lite") or not path.is_file():
        raise ValueError(f"Unknown profile '{name}'. Use full or lite.")
    return Profile(**yaml.safe_load(path.read_text()))
