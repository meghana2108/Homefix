"""Speech to text with mlx-whisper, from the local Hugging Face cache only."""

from __future__ import annotations

import functools
from dataclasses import dataclass
from pathlib import Path

import app.settings  # noqa: F401 - sets HF_HUB_OFFLINE before huggingface_hub is used
from app.contracts import MESSAGES, ModelUnavailable


@dataclass
class TranscriptResult:
    text: str                    # stripped transcript, "" when nothing was said
    seconds: float               # audio length
    mean_no_speech_prob: float   # mean over segments; 1.0 when there are no segments


@functools.lru_cache(maxsize=4)
def _resolve(repo: str) -> str:
    """Local folder of a cached repo. Never downloads."""
    from huggingface_hub import snapshot_download

    try:
        return snapshot_download(repo, local_files_only=True)
    except Exception as e:
        raise ModelUnavailable(MESSAGES["model_missing"].format(role="whisper")) from e


def _run(path: Path, model: str) -> dict:
    import mlx_whisper  # mlx_whisper keeps the loaded model between calls

    return mlx_whisper.transcribe(str(path), path_or_hf_repo=model)


def _seconds(path: Path) -> float:
    try:
        import soundfile as sf

        return float(sf.info(str(path)).duration)
    except Exception:  # noqa: BLE001 - length is display-only
        return 0.0


def transcribe(path: Path, repo: str) -> TranscriptResult:
    """Transcribe a (16 kHz mono WAV) file. Missing model -> ModelUnavailable."""
    result = _run(Path(path), _resolve(repo))
    probs = [float(s.get("no_speech_prob", 0.0)) for s in result.get("segments") or []]
    return TranscriptResult(
        text=str(result.get("text", "")).strip(),
        seconds=_seconds(Path(path)),
        mean_no_speech_prob=sum(probs) / len(probs) if probs else 1.0,
    )
