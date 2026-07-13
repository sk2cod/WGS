from datetime import date

from pydantic import BaseModel

from .enums import Approach, Format


class MemoryRecord(BaseModel):
    id: str
    date: date
    topic_id: str
    category: str                      # Topic.primary_category, denormalized for fast counting
    angle: str
    approach: Approach
    format: Format
    mood: str
    hook: str
    fingerprint: str                   # topic + angle + approach
    source_ids: list[str] = []
    status: str                        # draft | exported


def next_masthead_number(category: str, memory: list[MemoryRecord]) -> str:
    n = 1 + sum(1 for r in memory if r.category == category and r.status == "exported")
    return f"{category.upper()} NO. {n:02d}"
