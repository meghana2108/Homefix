"""Sentence embeddings (bge-small) for retrieval. Local, cached after first load."""

from __future__ import annotations

from functools import lru_cache

import numpy as np

from app.settings import load_profile


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(load_profile().models.embeddings)


def embed(texts: list[str]) -> np.ndarray:
    """L2-normalized float32 rows, one per text."""
    vecs = _model().encode(texts, normalize_embeddings=True, convert_to_numpy=True)
    return np.asarray(vecs, dtype=np.float32)
