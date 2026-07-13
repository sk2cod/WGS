"""Content memory read/write (blueprint Section 11). Supabase-backed in production
(constructed with no path); tests construct MemoryStore(path=...) to get the original
file-backed behavior instead, so they stay hermetic without touching the real database."""

from __future__ import annotations

import json
from pathlib import Path

from app.db import supabase as db
from app.models.brand_kit import BrandKit
from app.models.memory import MemoryRecord
from app.taxonomy.voice_register import APPROACH_REGISTER


class MemoryStore:
    def __init__(self, path: Path | None = None):
        self._path = path

    def load(self) -> list[MemoryRecord]:
        if self._path is None:
            return db.fetch_memory()
        if not self._path.exists():
            return []
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        return [MemoryRecord.model_validate(r) for r in raw]

    def save(self, records: list[MemoryRecord]) -> None:
        if self._path is None:
            raise NotImplementedError("bulk save isn't supported against Supabase; use append()")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps([r.model_dump(mode="json") for r in records], indent=2),
            encoding="utf-8",
        )

    def append(self, record: MemoryRecord) -> None:
        if self._path is None:
            db.append_memory(record)
            return
        records = self.load()
        records.append(record)
        self.save(records)


def append_voice_sample(brand_kit: BrandKit, approach_value: str, text: str) -> BrandKit:
    """Append approved copy to the register (poetic|direct) matching the post's approach
    via APPROACH_REGISTER. Returns a new BrandKit — callers are responsible for
    persisting it (no brand_kit store exists yet; that lands with routes/brand.py)."""
    register = APPROACH_REGISTER[approach_value]
    samples = brand_kit.voice_samples.model_copy(deep=True)
    getattr(samples, register).append(text)
    return brand_kit.model_copy(update={"voice_samples": samples})
