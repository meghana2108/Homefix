"""The ONLY file that opens answers.json (hard rule 2; tests/test_hard_rules.py checks this).

It loads each item's reference and hands it to eval/graders/<modality>.py::grade(item, ours, ref).
Graders never open files.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

from eval.pack import ID_KEYS, LIST_KEYS
from eval.types import GradeResult, PackItem, RunRecord

ANSWERS_FILE = "answers.json"


def refs_available(pack_dir: Path) -> bool:
    return (Path(pack_dir) / ANSWERS_FILE).is_file()


def load_refs(pack_dir: Path) -> dict[str, dict]:
    """item_id -> reference record."""
    data = json.loads((Path(pack_dir) / ANSWERS_FILE).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        rows = next((data[k] for k in LIST_KEYS if isinstance(data.get(k), list)), None)
        if rows is None:
            return {str(k): (v if isinstance(v, dict) else {"answer": v}) for k, v in data.items()}
        data = rows
    out: dict[str, dict] = {}
    for row in data:
        item_id = next((row[k] for k in ID_KEYS if k in row), None)
        if item_id is not None:
            out[str(item_id)] = row
    return out


def grade_run(records: list[RunRecord], items: dict[str, PackItem], refs: dict[str, dict]) -> list[GradeResult]:
    """One GradeResult per record. A missing item or reference, or a grader that raises, is
    recorded as a miss with a note; it never stops the run."""
    out: list[GradeResult] = []
    for rec in records:
        item = items.get(rec.item_id)
        if item is None:
            out.append(GradeResult(rec.item_id, "unknown_item", 0.0, False, "not in the pack"))
            continue
        ref = refs.get(rec.item_id)
        if ref is None:
            out.append(GradeResult(rec.item_id, "missing_ref", 0.0, False, "no reference"))
            continue
        try:
            grader = importlib.import_module(f"eval.graders.{item.modality}")
            out.append(grader.grade(item, rec, ref))
        except Exception as e:  # noqa: BLE001 - one bad item must not lose the whole run
            out.append(GradeResult(rec.item_id, "grader_error", 0.0, False, f"{type(e).__name__}: {e}"[:200]))
    return out
