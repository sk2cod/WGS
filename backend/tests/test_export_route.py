"""Tests for POST /export/confirm (logbook #35, #31/#33): the export-confirmation
event, real content persistence, voice-sample compounding (with its FIFO cap), the
malformed-slide validation guard, the masthead counter's dependence on real
status="exported" records, and the training-retry fix — content-persistence and
voice-training are two independent idempotency checks (status/exported_at vs.
voice_trained_at), so a training failure doesn't permanently forfeit the ability to
retry just the training half. LLMProvider/MemoryStore/brand_kit persistence are
monkeypatched at the route-module level so no real API call or Supabase write
happens, same pattern as test_generate_route_http.py."""

import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

import app.routes.export as export_module
from app.engine.memory import VOICE_SAMPLE_CAP, MemoryStore, append_voice_sample
from app.main import app
from app.models.enums import Approach, Format
from app.models.memory import MemoryRecord, next_masthead_number
from app.taxonomy.wgs_brand_kit import WGS_BRAND_KIT

client = TestClient(app)


class _QueueLLM:
    def __init__(self, responses):
        self._responses = list(responses)

    def complete(self, *, tier, system, prompt, max_tokens, cache=True):
        return self._responses.pop(0)


class _RaisingLLM:
    """Simulates a real training failure (rate limit, network, etc.) — not a parse
    fallback, which _extract_best_line already handles internally without raising."""

    def complete(self, *, tier, system, prompt, max_tokens, cache=True):
        raise RuntimeError("simulated LLM failure")


class _RecordingBrandKitDB:
    """Fakes just the one db.* function export.py calls — upsert_brand_kit — and
    records every call so tests can assert on how many times it fired and with what."""

    def __init__(self):
        self.upserted: list = []

    def upsert_brand_kit(self, kit):
        self.upserted.append(kit)


def _draft_record(
    record_id="m1", approach=Approach.STORY, category="Mindset", fingerprint="fp1"
) -> MemoryRecord:
    return MemoryRecord(
        id=record_id,
        date=date(2026, 1, 1),
        topic_id="t1",
        category=category,
        angle="a",
        approach=approach,
        format=Format.CAROUSEL,
        mood="wisdom",
        hook="hook",
        fingerprint=fingerprint,
        status="draft",
    )


_SLIDES = [{"template_id": "single_quote", "quote": "a quote about resting well"}]


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    store = MemoryStore(path=tmp_path / "memory.json")
    fake_db = _RecordingBrandKitDB()
    monkeypatch.setattr(export_module, "MemoryStore", lambda: store)
    monkeypatch.setattr(export_module, "get_brand_kit", lambda: WGS_BRAND_KIT)
    monkeypatch.setattr(export_module, "db", fake_db)
    return store, fake_db


def _confirm(memory_id, caption="c", slides=_SLIDES, train_voice=False):
    return client.post(
        "/export/confirm",
        json={"memory_id": memory_id, "caption": caption, "slides": slides, "train_voice": train_voice},
    )


def test_confirm_export_saves_content_and_marks_exported_train_voice_false(isolated, monkeypatch):
    store, fake_db = isolated
    store.append(_draft_record())
    monkeypatch.setattr(export_module, "LLMProvider", lambda: _QueueLLM([]))

    res = _confirm("m1", caption="final caption", train_voice=False)
    assert res.status_code == 200
    assert res.json() == {
        "memory_id": "m1",
        "status": "exported",
        "already_exported": False,
        "voice_training_status": "not_requested",
    }

    saved = store.get("m1")
    assert saved.status == "exported"
    assert saved.caption == "final caption"
    assert saved.exported_at is not None
    assert saved.voice_trained_at is None  # untouched -- training was never requested
    assert len(saved.slides) == 1
    assert saved.slides[0].template_id == "single_quote"
    assert fake_db.upserted == []


def test_confirm_export_appends_and_sets_voice_trained_at_on_first_success(isolated, monkeypatch):
    store, fake_db = isolated
    store.append(_draft_record())
    monkeypatch.setattr(
        export_module, "LLMProvider", lambda: _QueueLLM([json.dumps({"best_line": "line one"})])
    )

    res = _confirm("m1", caption="final caption", train_voice=True)
    assert res.status_code == 200
    body = res.json()
    assert body["already_exported"] is False
    assert body["voice_training_status"] == "appended"
    assert len(fake_db.upserted) == 1
    assert "line one" in fake_db.upserted[0].voice_samples.poetic

    saved = store.get("m1")
    assert saved.status == "exported"
    assert saved.voice_trained_at is not None


def test_confirm_export_repeat_call_after_success_is_already_trained_no_double_append(
    isolated, monkeypatch
):
    store, fake_db = isolated
    store.append(_draft_record())
    # Only one queued response -- if the already-trained skip ever let a second call
    # through to _extract_best_line, this raises IndexError on an empty queue and the
    # test fails loudly, rather than silently double-appending.
    monkeypatch.setattr(
        export_module, "LLMProvider", lambda: _QueueLLM([json.dumps({"best_line": "line one"})])
    )

    first = _confirm("m1", caption="final caption", train_voice=True)
    assert first.status_code == 200
    assert first.json()["voice_training_status"] == "appended"
    assert len(fake_db.upserted) == 1
    first_trained_at = store.get("m1").voice_trained_at

    second = _confirm("m1", caption="a different caption", train_voice=True)
    assert second.status_code == 200
    body = second.json()
    assert body["already_exported"] is True  # content half was already done too
    assert body["voice_training_status"] == "already_trained"
    assert len(fake_db.upserted) == 1  # no second upsert
    saved = store.get("m1")
    assert saved.caption == "final caption"  # content untouched by the no-op retry
    assert saved.voice_trained_at == first_trained_at  # untouched, not re-stamped


def test_confirm_export_training_failure_leaves_retryable_and_a_later_retry_succeeds(
    isolated, monkeypatch
):
    store, fake_db = isolated
    store.append(_draft_record())
    monkeypatch.setattr(export_module, "LLMProvider", lambda: _RaisingLLM())

    first = _confirm("m1", caption="final caption", train_voice=True)
    assert first.status_code == 200  # the request itself succeeds -- content is saved
    body = first.json()
    assert body["already_exported"] is False
    assert body["voice_training_status"] == "failed"
    assert fake_db.upserted == []  # nothing was appended on the failed attempt

    saved = store.get("m1")
    assert saved.status == "exported"  # content persistence is unaffected by the failure
    assert saved.caption == "final caption"
    assert saved.voice_trained_at is None  # left unset -- this is the retryable state

    # Retry: same memory_id, train_voice again, this time a working LLM. Previously
    # (before this fix) this was impossible -- the old shared idempotency guard on
    # `status` alone would have short-circuited this as a pure no-op, permanently
    # forfeiting the training half.
    monkeypatch.setattr(
        export_module, "LLMProvider", lambda: _QueueLLM([json.dumps({"best_line": "recovered line"})])
    )
    second = _confirm("m1", caption="final caption", train_voice=True)
    assert second.status_code == 200
    body2 = second.json()
    assert body2["already_exported"] is True  # content was already saved from attempt 1
    assert body2["voice_training_status"] == "appended"  # but training now succeeds
    assert len(fake_db.upserted) == 1
    assert "recovered line" in fake_db.upserted[0].voice_samples.poetic

    saved2 = store.get("m1")
    assert saved2.voice_trained_at is not None


def test_confirm_export_resolves_register_from_stored_approach_not_client(isolated, monkeypatch):
    store, fake_db = isolated
    store.append(_draft_record(record_id="m-direct", approach=Approach.EDUCATIONAL, fingerprint="fp-direct"))
    monkeypatch.setattr(
        export_module, "LLMProvider", lambda: _QueueLLM([json.dumps({"best_line": "a direct line"})])
    )

    res = _confirm("m-direct", train_voice=True)
    assert res.status_code == 200
    assert res.json()["voice_training_status"] == "appended"
    updated_kit = fake_db.upserted[0]
    assert "a direct line" in updated_kit.voice_samples.direct
    assert "a direct line" not in updated_kit.voice_samples.poetic


def test_confirm_export_rejects_malformed_slide_template_id(isolated):
    store, fake_db = isolated
    store.append(_draft_record())

    res = client.post(
        "/export/confirm",
        json={
            "memory_id": "m1",
            "caption": "c",
            "slides": [{"template_id": "not_a_real_template", "whatever": "x"}],
            "train_voice": False,
        },
    )
    assert res.status_code == 422  # rejected at the request-validation boundary

    saved = store.get("m1")
    assert saved.status == "draft"  # never reached the handler, let alone the store
    assert saved.slides == []
    assert fake_db.upserted == []


def test_confirm_export_missing_template_id_also_rejected(isolated):
    store, _ = isolated
    store.append(_draft_record())

    res = client.post(
        "/export/confirm",
        json={
            "memory_id": "m1",
            "caption": "c",
            "slides": [{"quote": "no template_id at all"}],
            "train_voice": False,
        },
    )
    assert res.status_code == 422


def test_confirm_export_unknown_memory_id_404s(isolated):
    res = _confirm("does-not-exist")
    assert res.status_code == 404


def test_append_voice_sample_fifo_cap_evicts_oldest_at_10():
    kit = WGS_BRAND_KIT.model_copy(deep=True)
    kit.voice_samples.poetic = [f"seed-{i}" for i in range(VOICE_SAMPLE_CAP)]
    assert len(kit.voice_samples.poetic) == VOICE_SAMPLE_CAP

    updated = append_voice_sample(kit, Approach.STORY.value, "new-line")

    assert len(updated.voice_samples.poetic) == VOICE_SAMPLE_CAP  # still capped, not 11
    assert "seed-0" not in updated.voice_samples.poetic  # oldest evicted
    assert updated.voice_samples.poetic[0] == "seed-1"  # FIFO: next-oldest now first
    assert updated.voice_samples.poetic[-1] == "new-line"  # newest at the end


def test_append_voice_sample_below_cap_just_appends():
    kit = WGS_BRAND_KIT.model_copy(deep=True)
    kit.voice_samples.direct = [f"seed-{i}" for i in range(VOICE_SAMPLE_CAP - 1)]

    updated = append_voice_sample(kit, Approach.EDUCATIONAL.value, "new-line")

    assert len(updated.voice_samples.direct) == VOICE_SAMPLE_CAP
    assert "seed-0" in updated.voice_samples.direct  # nothing evicted below the cap
    assert updated.voice_samples.direct[-1] == "new-line"


def test_masthead_number_increments_after_real_export_confirm(isolated, monkeypatch):
    store, _ = isolated
    store.append(_draft_record(record_id="m1", category="Mindset", fingerprint="fp1"))
    store.append(_draft_record(record_id="m2", category="Mindset", fingerprint="fp2"))
    monkeypatch.setattr(export_module, "LLMProvider", lambda: _QueueLLM([]))

    assert next_masthead_number("Mindset", store.load()) == "MINDSET NO. 01"

    res = _confirm("m1", train_voice=False)
    assert res.status_code == 200

    assert next_masthead_number("Mindset", store.load()) == "MINDSET NO. 02"
