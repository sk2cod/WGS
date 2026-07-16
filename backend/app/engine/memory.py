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

    def get(self, record_id: str) -> MemoryRecord | None:
        if self._path is None:
            return db.fetch_memory_by_id(record_id)
        for record in self.load():
            if record.id == record_id:
                return record
        return None

    def update(self, record: MemoryRecord) -> None:
        if self._path is None:
            db.update_memory(record)
            return
        records = [record if r.id == record.id else r for r in self.load()]
        self.save(records)


VOICE_SAMPLE_CAP = 10


def append_voice_sample(brand_kit: BrandKit, approach_value: str, text: str) -> BrandKit:
    """Append approved copy to the register (poetic|direct) matching the post's approach
    via APPROACH_REGISTER. Returns a new BrandKit — callers are responsible for
    persisting it (routes/export.py calls db.upsert_brand_kit() with the result).

    Enforces a FIFO cap of VOICE_SAMPLE_CAP entries per register (logbook #35): once
    a register is at the cap, the oldest sample is dropped before the new one is
    appended, so the compounding mechanism can't grow the few-shot block unbounded."""
    register = APPROACH_REGISTER[approach_value]
    samples = brand_kit.voice_samples.model_copy(deep=True)
    register_list = getattr(samples, register)
    if len(register_list) >= VOICE_SAMPLE_CAP:
        del register_list[0]
    register_list.append(text)
    return brand_kit.model_copy(update={"voice_samples": samples})
