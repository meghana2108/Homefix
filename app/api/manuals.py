"""GET /api/manuals. Returns [] until the manual layer (M13) lists data/manuals/*.pdf."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/api/manuals")
def manuals() -> list[dict]:
    return []
