import pymupdf
from fastapi.testclient import TestClient

from app.api.main import app
from app.pipelines import text


def pdf(path, n):
    d = pymupdf.open()
    for i in range(n):
        d.new_page().insert_text((72, 72), f"page {i}")
    d.save(path)


def test_lists_manuals(tmp_path, monkeypatch):
    monkeypatch.setattr(text, "MANUALS_DIR", tmp_path)
    pdf(tmp_path / "b.pdf", 2)
    pdf(tmp_path / "a.pdf", 1)
    pdf(tmp_path / "has space.pdf", 1)
    r = TestClient(app).get("/api/manuals").json()
    assert [(m["id"], m["pages"]) for m in r] == [("a", 1), ("b", 2)]
    assert r[0]["title"] == "a.pdf"


def test_missing_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(text, "MANUALS_DIR", tmp_path / "nope")
    assert TestClient(app).get("/api/manuals").json() == []
