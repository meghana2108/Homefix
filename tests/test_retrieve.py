import numpy as np
import pytest

from app.models import embeddings
from app.text.retrieve import chunk_pages, top_chunks

PAGES = [
    "Error E21 means the water did not drain. Clean the drain pump filter every month.",
    "To level the washer, turn the front feet. Use a spirit level on the lid.",
]


def test_chunks_keep_pages():
    pages = [" ".join(f"a{i}" for i in range(400)), " ".join(f"b{i}" for i in range(400))]
    chunks = chunk_pages(pages)
    assert {c.page for c in chunks} == {1, 2}
    assert chunks[0].text.split()[0] == "a0"


def test_top_chunks_finds_level_page(monkeypatch):
    vocab: dict[str, int] = {}

    def fake_embed(texts):
        rows = np.zeros((len(texts), 64), dtype=np.float32)
        for r, t in enumerate(texts):
            for w in t.lower().replace(",", " ").replace(".", " ").split():
                rows[r, vocab.setdefault(w, len(vocab)) % 64] += 1
            n = np.linalg.norm(rows[r])
            rows[r] /= n or 1
        return rows

    monkeypatch.setattr(embeddings, "embed", fake_embed)
    assert top_chunks("how do I level the washer", chunk_pages(PAGES), 1)[0].page == 2
    assert top_chunks("x", [], 3) == []


@pytest.mark.model
def test_real_embed_shape():
    assert embeddings.embed(["a", "b"]).shape == (2, 384)
