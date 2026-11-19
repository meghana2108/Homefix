"""GET /api/manuals: the PDFs in data/manuals/ that can be picked as a manual."""

from __future__ import annotations

from fastapi import APIRouter

from app.pipelines.homefix import list_manuals

router = APIRouter()


@router.get("/api/manuals")
def manuals() -> list[dict]:
    return list_manuals()
