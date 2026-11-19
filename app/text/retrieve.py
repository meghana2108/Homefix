"""Find the right pages in long manuals: BM25 plus embeddings, fused by rank."""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
from rank_bm25 import BM25Okapi

from app.models import embeddings


@dataclass
class Chunk:
    text: str
    page: int  # 1-based


def chunk_pages(pages: list[str], size: int = 350, overlap: int = 50) -> list[Chunk]:
    step = max(1, size - overlap)
    out: list[Chunk] = []
    for n, page in enumerate(pages, start=1):
        words = page.split()
        for start in range(0, len(words), step):
            out.append(Chunk(" ".join(words[start:start + size]), n))
            if start + size >= len(words):
                break
    return out


def _tokens(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def top_chunks(question: str, chunks: list[Chunk], k: int) -> list[Chunk]:
    if not chunks:
        return []
    bm25 = BM25Okapi([_tokens(c.text) or [""] for c in chunks])
    bm = np.asarray(bm25.get_scores(_tokens(question)))
    bm_rank = [i for i in np.argsort(-bm, kind="stable")[:20] if bm[i] > 0]
    vecs = embeddings.embed([c.text for c in chunks] + [question])
    sims = vecs[:-1] @ vecs[-1]
    em_rank = list(np.argsort(-sims, kind="stable")[:20])
    fused: dict[int, float] = {}
    for ranking in (bm_rank, em_rank):
        for r, i in enumerate(ranking):
            fused[int(i)] = fused.get(int(i), 0.0) + 1.0 / (60 + r + 1)
    best = sorted(fused, key=lambda i: -fused[i])[:k]
    return [chunks[i] for i in best]
