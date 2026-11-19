"""Zero-shot sound labels with CLAP over our own vocabulary (AudioSet-derived + appliances).

Hard rule 3: the vocabulary is config/sound_labels/general.txt + appliances.txt, never ESC-50.
The label texts are embedded once per (repo, vocabulary) and cached, so a call only embeds the
audio (~0.05 s on the M2 instead of ~2 s for transformers' pipeline, same scores).
"""

from __future__ import annotations

import functools
import threading
from pathlib import Path

import app.settings  # noqa: F401 - sets HF_HUB_OFFLINE / TRANSFORMERS_OFFLINE first
from app.contracts import MESSAGES, ModelUnavailable, SoundLabel
from app.settings import SOUND_LABEL_FILES

TEMPLATE = "This is a sound of {}."  # same as scripts/go_no_go.py
_lock = threading.Lock()


def load_vocab() -> list[str]:
    """general.txt then appliances.txt; '#' lines and blanks dropped; duplicates removed, order kept."""
    seen: set[str] = set()
    out: list[str] = []
    for f in SOUND_LABEL_FILES:
        for line in f.read_text(encoding="utf-8").splitlines():
            label = line.strip()
            if label and not label.startswith("#") and label not in seen:
                seen.add(label)
                out.append(label)
    return out


@functools.lru_cache(maxsize=2)
def _load(repo: str):
    """The transformers pipeline (we use its model, tokenizer and feature extractor)."""
    try:
        import numpy as np
        import torch
        from transformers import pipeline

        clf = pipeline("zero-shot-audio-classification", model=repo)
        fe = clf.feature_extractor
        with torch.no_grad():  # the first audio forward on MPS is slow (~15 s); pay it at load time
            silence = fe([np.zeros(fe.sampling_rate, dtype=np.float32)], sampling_rate=fe.sampling_rate,
                         return_tensors="pt").to(clf.model.device)
            clf.model.get_audio_features(**silence)
        return clf
    except Exception as e:
        raise ModelUnavailable(MESSAGES["model_missing"].format(role="sound")) from e


def _embedding(out):
    import torch

    emb = out if torch.is_tensor(out) else out.pooler_output  # transformers 5 returns an output object
    return emb / emb.norm(dim=-1, keepdim=True)


@functools.lru_cache(maxsize=4)
def _text_embeds(repo: str, labels: tuple[str, ...]):
    import torch

    clf = _load(repo)
    with torch.no_grad():
        tokens = clf.tokenizer([TEMPLATE.format(lb) for lb in labels], padding=True,
                               return_tensors="pt").to(clf.model.device)
        return _embedding(clf.model.get_text_features(**tokens))


def _score(path: Path, repo: str, labels: list[str]) -> list[tuple[str, float]]:
    """Softmax over all labels, in label order (same maths as transformers' pipeline)."""
    import torch
    from transformers.pipelines.audio_utils import ffmpeg_read

    clf = _load(repo)
    fe = clf.feature_extractor
    # Decode with ffmpeg like transformers' pipeline does (librosa resamples differently and
    # shifts scores by up to ~0.1 on 44.1 kHz input).
    audio = ffmpeg_read(Path(path).read_bytes(), fe.sampling_rate)
    with _lock, torch.no_grad():
        text = _text_embeds(repo, tuple(labels))
        feats = fe([audio], sampling_rate=fe.sampling_rate, return_tensors="pt").to(clf.model.device)
        audio_emb = _embedding(clf.model.get_audio_features(**feats))
        probs = ((audio_emb @ text.T) * clf.model.logit_scale_a.exp()).softmax(-1)[0].float().cpu()
    return list(zip(labels, probs.tolist(), strict=True))


def classify(path: Path, repo: str, labels: list[str], top_k: int = 3) -> list[SoundLabel]:
    """Top-k labels, highest score first. Missing model -> ModelUnavailable."""
    scored = sorted(_score(Path(path), repo, labels), key=lambda s: s[1], reverse=True)
    return [SoundLabel(label=label, score=float(score)) for label, score in scored[:top_k]]
