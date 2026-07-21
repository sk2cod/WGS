"""POST /poc/generate — isolated POC route, deliberately separate from
routes/generate.py. Same logic as scripts/poc_writer.py (both call
app.poc.writer.run_poc_writer): one Sonnet call, the verbatim POC system prompt,
no Haiku, no angle/approach/entry_point sampling, no critique/refine loop.

Does not import from, and is not imported by, routes/generate.py, engine/generator.py,
engine/angle_engine.py, engine/validator.py, or engine/memory.py — nothing about the
existing /generate pipeline is read or written by this file."""

from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.poc.writer import run_poc_writer
from app.taxonomy.loader import get_topics_by_id

router = APIRouter(prefix="/poc")


class PocGenerateRequest(BaseModel):
    topic_id: str  # a real id from taxonomy/topics.yaml
    # Test-harness-only knob (see app/poc/FINDINGS.md #1) — an in-memory list the
    # caller passes by hand per test batch, not a persisted/production mechanism.
    recent_anchors: list[str] = []
    # "current" (default, app/poc/prompt.py) or "gpt" (app/poc/prompt_gpt_variant.py)
    # — A/B comparison only, does not change behavior for any existing caller.
    variant: Literal["current", "gpt"] = "current"


class PocGenerateResponse(BaseModel):
    topic_id: str
    topic_name: str
    slides: list[str]
    conversation_question: str
    caption: str


@router.post("/generate", response_model=PocGenerateResponse)
def poc_generate(req: PocGenerateRequest) -> PocGenerateResponse:
    topics_by_id = get_topics_by_id()
    topic = topics_by_id.get(req.topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail=f"Unknown topic_id: {req.topic_id!r}")

    raw_json = run_poc_writer(
        topic.name, recent_anchors=req.recent_anchors or None, variant=req.variant
    )
    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Model did not return valid JSON: {exc}. Raw output: {raw_json[:500]}",
        ) from exc

    try:
        return PocGenerateResponse(
            topic_id=topic.id,
            topic_name=topic.name,
            slides=parsed["slides"],
            conversation_question=parsed["conversation_question"],
            caption=parsed["caption"],
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Model JSON missing expected field: {exc}. Raw output: {raw_json[:500]}",
        ) from exc
