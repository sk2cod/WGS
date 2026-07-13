from datetime import date

from app.engine.memory import MemoryStore, append_voice_sample
from app.models.enums import Approach, Format
from app.models.memory import MemoryRecord
from app.taxonomy.wgs_brand_kit import WGS_BRAND_KIT


def _record(fingerprint="fp") -> MemoryRecord:
    return MemoryRecord(
        id="m1",
        date=date(2026, 1, 1),
        topic_id="t1",
        category="Mindset",
        angle="a",
        approach=Approach.STORY,
        format=Format.CAROUSEL,
        mood="wisdom",
        hook="h",
        fingerprint=fingerprint,
        status="draft",
    )


def test_memory_store_starts_empty(tmp_path):
    store = MemoryStore(path=tmp_path / "memory.json")
    assert store.load() == []


def test_memory_store_append_and_load_roundtrips(tmp_path):
    store = MemoryStore(path=tmp_path / "memory.json")
    store.append(_record())
    loaded = store.load()
    assert len(loaded) == 1
    assert loaded[0].fingerprint == "fp"


def test_memory_store_persists_across_instances(tmp_path):
    path = tmp_path / "memory.json"
    MemoryStore(path=path).append(_record("fp-1"))
    MemoryStore(path=path).append(_record("fp-2"))
    records = MemoryStore(path=path).load()
    assert {r.fingerprint for r in records} == {"fp-1", "fp-2"}


def test_append_voice_sample_appends_to_poetic_for_story_approach():
    updated = append_voice_sample(WGS_BRAND_KIT, Approach.STORY.value, "a new poetic line")
    assert "a new poetic line" in updated.voice_samples.poetic
    assert "a new poetic line" not in WGS_BRAND_KIT.voice_samples.poetic


def test_append_voice_sample_appends_to_direct_for_educational_approach():
    updated = append_voice_sample(WGS_BRAND_KIT, Approach.EDUCATIONAL.value, "a new direct line")
    assert "a new direct line" in updated.voice_samples.direct
    assert "a new direct line" not in WGS_BRAND_KIT.voice_samples.direct
