"""GET /topics — the full authored catalog, for Home's browse view and the generate
page's topic picker (the 3 daily picks alone aren't the whole evergreen catalog,
blueprint Section 10)."""

from __future__ import annotations

from fastapi import APIRouter

from app.models.topic import Topic
from app.taxonomy.loader import get_topics

router = APIRouter()


@router.get("/topics", response_model=list[Topic])
def list_topics() -> list[Topic]:
    return list(get_topics())
