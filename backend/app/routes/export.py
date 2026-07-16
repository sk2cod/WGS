"""POST /export/confirm — the export-confirmation event (logbook #35, #31/#33) that
never existed before: a draft MemoryRecord becomes "exported" with real content, and
the masthead counter (which only ever counts status == "exported" records) starts
incrementing for real as a direct consequence. Optionally trains the voice-compounding
mechanism (blueprint Section 4) by picking the single best line from the final,
as-exported content and appending it to the matching register.

Content-persistence and voice-training are two independent idempotency checks, not
one shared guard (logbook #35 fix) — a record's `status`/`exported_at` govern whether
content gets (re-)saved; `voice_trained_at` alone governs whether training has
genuinely completed. A training failure leaves `voice_trained_at` as None so a later
call with the same memory_id can retry just the training half, without needing to
(and being unable to, since content is already saved) re-run export confirmation."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db import supabase as db
from app.engine.generator import slide_text
from app.engine.memory import MemoryStore, append_voice_sample
from app.models.memory import MemoryRecord
from app.models.post import Slide
from app.providers.llm import LLMProvider, strip_json_fence
from app.taxonomy.wgs_brand_kit import get_brand_kit

logger = logging.getLogger(__name__)

router = APIRouter()

VoiceTrainingStatus = Literal["appended", "already_trained", "not_requested", "failed"]


class ExportConfirmRequest(BaseModel):
    memory_id: str
    caption: str
    # The real discriminated-union type, not a raw dict/list[Any] — FastAPI validates
    # every slide through CoverSlide/BodySlide/BodyTeachingSlide/ClosingSlide/
    # QuoteSlide/StatSlide (via template_id) at the API boundary, before this handler
    # ever runs. A malformed or unexpected template_id is rejected with a 422 here,
    # never reaches MemoryStore.update(), and can never land in Postgres as something
    # nothing can deserialize later.
    slides: list[Slide]
    train_voice: bool = False


class ExportConfirmResponse(BaseModel):
    memory_id: str
    status: str
    # True if the record's status was already "exported" *before* this call (content
    # was not re-persisted this time) — describes the content-persist half only.
    already_exported: bool
    # Describes the training half independently of the above:
    #   "appended"        — training ran on this call and genuinely succeeded
    #   "already_trained" — voice_trained_at was already set; skipped, no double-append
    #   "not_requested"   — train_voice was false; training untouched either way
    #   "failed"          — training was attempted this call and raised; retryable later
    voice_training_status: VoiceTrainingStatus


def _extract_best_line(caption: str, slides: list[Slide], llm: LLMProvider) -> str:
    """Cheap-tier call reading the real, final (post-edit) content to pick the single
    line most worth keeping as a brand-voice example. Never raises on a parse failure —
    falls back to the first slide's text (or the caption, if there are no slides), same
    defensive pattern as angle_engine._parse_angle_response. Callers still need to
    handle the LLM call itself raising (rate limit, network, etc.) — that's a real
    training failure, not a parse fallback."""
    slide_lines = [slide_text(s) for s in slides]
    content = "\n".join([*slide_lines, f"Caption: {caption}"])

    system = (
        "You pick exactly one line from a finished Instagram post that best represents "
        "the brand's voice — the single most quotable, reusable sentence, suitable as a "
        "brand-voice example for future writing. Prefer a complete, self-contained "
        "sentence over a fragment; prefer something that reads well entirely on its own, "
        "out of context.\n"
        'Respond with ONLY JSON, no markdown fence: {"best_line": "..."}'
    )
    prompt = f"Post content:\n{content}"

    raw = llm.complete(tier="cheap", system=system, prompt=prompt, max_tokens=200)
    line = ""
    try:
        data = json.loads(strip_json_fence(raw))
        line = str(data.get("best_line") or "").strip()
    except (json.JSONDecodeError, AttributeError):
        pass

    if line:
        return line
    return slide_lines[0] if slide_lines else caption


def _attempt_voice_training(record: MemoryRecord) -> MemoryRecord:
    """Runs the extraction -> append -> upsert sequence and returns the record with
    voice_trained_at set, only once every step has genuinely succeeded. Raises on any
    failure (never swallows) so the caller's try/except can log it and report "failed"
    without setting voice_trained_at — leaving the record retryable."""
    llm = LLMProvider()
    best_line = _extract_best_line(record.caption, record.slides, llm)
    if not best_line:
        raise ValueError("no best_line could be extracted from the final content")
    brand_kit = get_brand_kit()
    updated_kit = append_voice_sample(brand_kit, record.approach.value, best_line)
    db.upsert_brand_kit(updated_kit)
    return record.model_copy(update={"voice_trained_at": datetime.now(timezone.utc)})


@router.post("/export/confirm", response_model=ExportConfirmResponse)
async def confirm_export(request: ExportConfirmRequest) -> ExportConfirmResponse:
    store = MemoryStore()
    record = store.get(request.memory_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Unknown memory_id: {request.memory_id!r}")

    already_exported = record.status == "exported"
    if not already_exported:
        record = record.model_copy(
            update={
                "status": "exported",
                "exported_at": datetime.now(timezone.utc),
                "caption": request.caption,
                "slides": request.slides,
            }
        )
        store.update(record)
    # else: content already saved from an earlier confirm — don't touch it again.
    # Training below still runs off `record`'s real, already-saved content either way.

    voice_training_status: VoiceTrainingStatus
    if not request.train_voice:
        voice_training_status = "not_requested"
    elif record.voice_trained_at is not None:
        voice_training_status = "already_trained"
    else:
        try:
            record = _attempt_voice_training(record)
            store.update(record)
            voice_training_status = "appended"
        except Exception:
            logger.exception(
                "voice training failed for memory_id=%s (approach=%s) — voice_trained_at "
                "left unset so a later confirm call can retry it",
                record.id,
                record.approach.value,
            )
            voice_training_status = "failed"

    return ExportConfirmResponse(
        memory_id=record.id,
        status=record.status,
        already_exported=already_exported,
        voice_training_status=voice_training_status,
    )
