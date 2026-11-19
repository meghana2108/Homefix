"""The one adapter that knows the practice pack's format. Reads items.json only.

The pack isn't downloaded yet, so the key names below are guesses that cover the likely shapes
(they match scripts/go_no_go.py: "modality", "file", "question"). When the pack arrives, fix the
constants here and nowhere else. Never copy pack content into tests or docs (hard rule 1).
"""

from __future__ import annotations

import json
from pathlib import Path

from app.contracts import Attachment
from eval.types import PackItem

ITEMS_FILE = "items.json"
LIST_KEYS = ("items", "data")                         # {"items": [...]} wrappers
ID_KEYS = ("id", "item_id", "uid")
MODALITY_KEYS = ("modality", "type", "category", "task")
QUESTION_KEYS = ("question", "prompt", "query", "instruction")
FILE_KEYS = ("file", "path", "media", "filename", "audio", "image", "video", "document")
INLINE_DOC_KEYS = ("context", "document_text", "passage", "text")
TEST_KEYS = ("test", "test_file", "test_path", "tests")
CODE_TEST_DIR = Path("code") / "tests"               # EVAL.md: code/tests/<id>_test.py

MODALITIES = {"image", "audio", "text", "code", "video"}
SYNONYMS = {"speech": "audio", "sound": "audio", "sounds": "audio", "asr": "audio",
            "vision": "image", "photo": "image", "document": "text", "doc": "text", "qa": "text",
            "programming": "code", "clip": "video"}


def _first(d: dict, keys: tuple[str, ...]):
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return k, d[k]
    return None, None


def _raw_items(data) -> list[dict]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for k in LIST_KEYS:
            if isinstance(data.get(k), list):
                return data[k]
        # {"<id>": {...}, ...}
        return [{"id": k, **v} for k, v in data.items() if isinstance(v, dict)]
    raise ValueError(f"{ITEMS_FILE}: expected a list or an object of items")


def _item(raw: dict, index: int, pack_dir: Path) -> PackItem:
    _, item_id = _first(raw, ID_KEYS)
    item_id = str(item_id) if item_id is not None else f"item-{index}"
    _, mod_raw = _first(raw, MODALITY_KEYS)
    sub = str(mod_raw or "").strip().lower()
    modality = sub if sub in MODALITIES else SYNONYMS.get(sub)
    if modality is None:
        raise ValueError(f"item {item_id}: unknown modality {sub!r}")

    used = set()
    q_key, question = _first(raw, QUESTION_KEYS)
    used.add(q_key)
    meta: dict = {"subtype": sub}  # e.g. "speech" vs "sounds" for audio

    path = None
    f_key, f_val = _first(raw, FILE_KEYS)
    if isinstance(f_val, str) and (pack_dir / f_val).suffix:
        path, _ = pack_dir / f_val, used.add(f_key)

    if modality == "text" and path is None:
        d_key, doc = _first(raw, INLINE_DOC_KEYS)
        if isinstance(doc, str) and d_key != q_key:
            meta["inline_document"], _ = doc, used.add(d_key)

    if modality == "code":
        t_key, t_val = _first(raw, TEST_KEYS)
        if isinstance(t_val, str) and (pack_dir / t_val).is_file():
            meta["test_path"], _ = pack_dir / t_val, used.add(t_key)
        elif (pack_dir / CODE_TEST_DIR / f"{item_id}_test.py").is_file():
            meta["test_path"] = pack_dir / CODE_TEST_DIR / f"{item_id}_test.py"

    skip = used | set(ID_KEYS) | set(MODALITY_KEYS)
    meta.update({k: v for k, v in raw.items() if k not in skip})  # a pack's own "subtype" wins
    return PackItem(id=item_id, modality=modality, question=str(question or ""), path=path, meta=meta)


def load_items(pack_dir: Path) -> list[PackItem]:
    pack_dir = Path(pack_dir)
    data = json.loads((pack_dir / ITEMS_FILE).read_text(encoding="utf-8"))
    return [_item(raw, i, pack_dir) for i, raw in enumerate(_raw_items(data))]


def to_attachments(item: PackItem) -> list[Attachment] | None:
    """Prefilled attachments for handle(), or None to let handle() convert item.path."""
    doc = item.meta.get("inline_document")
    if isinstance(doc, str):
        return [Attachment(path=None, kind="document", original_name=f"{item.id}.txt", pages=[doc])]
    return None
