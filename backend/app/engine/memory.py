"""Content memory read/write (blueprint Section 11). File-backed for now — no Supabase
wiring until Phase 6 — but kept behind a small store class so swapping the backing store
later doesn't touch callers."""

from __future__ import annotations

import json
from pathlib import Path

from app.models.brand_kit import BrandKit
from app.models.memory import MemoryRecord
from app.taxonomy.voice_register import APPROACH_REGISTER

MEMORY_PATH = Path(__file__).resolve().parent.parent.parent / ".cache" / "memory.json"


class MemoryStore:
    def __init__(self, path: Path = MEMORY_PATH):
        self._path = path

    def load(self) -> list[MemoryRecord]:
        if not self._path.exists():
            return []
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        return [MemoryRecord.model_validate(r) for r in raw]

    def save(self, records: list[MemoryRecord]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps([r.model_dump(mode="json") for r in records], indent=2),
            encoding="utf-8",
        )

    def append(self, record: MemoryRecord) -> None:
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
