"""audio grader. STUB from A7; Akshayaa (A9) replaces the body. Metrics: docs/EVAL.md."""

from __future__ import annotations

from eval.types import GradeResult, PackItem, RunRecord


def grade(item: PackItem, ours: RunRecord, ref: dict) -> GradeResult:
    return GradeResult(item_id=item.id, metric="todo", score=0.0, hit=False, note="not built")
