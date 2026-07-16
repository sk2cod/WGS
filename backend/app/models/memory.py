from datetime import date, datetime

from pydantic import BaseModel, Field

from .enums import Approach, Format
from .post import Slide


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
    # Real content + export timestamp (logbook #35, #31/#33) -- populated by
    # routes/export.py's confirm endpoint, not at /generate time (a "draft" record
    # has neither yet). `slides` is the same discriminated-union shape as
    # GeneratedPost.slides -- Pydantic validates it through that union on read
    # (Supabase jsonb -> MemoryRecord) exactly the same way routes/export.py
    # validates it on write, so a malformed template_id can never round-trip either
    # direction as opaque JSON.
    caption: str = ""
    slides: list[Slide] = Field(default_factory=list)
    exported_at: datetime | None = None
    # NULL means training hasn't successfully completed yet -- deliberately decoupled
    # from `status`/`exported_at` (logbook #35) so a training failure doesn't
    # permanently forfeit the ability to retry just the training half.
    voice_trained_at: datetime | None = None


def next_masthead_number(category: str, memory: list[MemoryRecord]) -> str:
    n = 1 + sum(1 for r in memory if r.category == category and r.status == "exported")
    return f"{category.upper()} NO. {n:02d}"
