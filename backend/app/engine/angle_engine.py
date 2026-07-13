"""Angle engine — samples one (sub-concept x approach x entry-point) cell from a Topic
and the two global lists, then asks the cheap tier to write the specific angle sentence
and tag the post's mood in the same call (blueprint Section 5)."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass

from app.models.enums import Approach, EntryPoint
from app.models.memory import MemoryRecord
from app.models.topic import Topic
from app.providers.llm import LLMProvider, strip_json_fence
from app.taxonomy.approaches import APPROACHES
from app.taxonomy.entry_points import ENTRY_POINTS

VALID_MOODS = {"wisdom", "bold", "celebratory"}
DEFAULT_MOOD = "wisdom"


@dataclass
class SampledAngle:
    sub_concept: str
    approach: Approach
    entry_point: EntryPoint
    angle: str
    mood: str
    reason: str
    fingerprint: str


def _fingerprint(topic_id: str, sub_concept: str, approach: Approach) -> str:
    return f"{topic_id}:{sub_concept}:{approach.value}"


def sample_cell(
    topic: Topic,
    memory: list[MemoryRecord],
    *,
    rng: random.Random | None = None,
) -> tuple[str, Approach, EntryPoint]:
    """Pick one (sub-concept, approach, entry-point) cell, excluding combinations whose
    topic+sub-concept+approach fingerprint already appears in this topic's memory. Falls
    back to the full pool once every combination for this topic has been used."""
    rng = rng or random.Random()
    used_fingerprints = {r.fingerprint for r in memory if r.topic_id == topic.id}

    candidates = [
        (sub, Approach(a), EntryPoint(e))
        for sub in topic.seed_angles
        for a in APPROACHES
        for e in ENTRY_POINTS
    ]
    unused = [c for c in candidates if _fingerprint(topic.id, c[0], c[1]) not in used_fingerprints]
    pool = unused or candidates
    return rng.choice(pool)


def _parse_angle_response(
    raw: str, *, fallback_angle: str, fallback_reason: str
) -> tuple[str, str, str]:
    angle, mood, reason = "", "", ""
    try:
        data = json.loads(strip_json_fence(raw))
        angle = str(data.get("angle") or "").strip()
        mood = str(data.get("mood") or "").strip().lower()
        reason = str(data.get("reason") or "").strip()
    except (json.JSONDecodeError, AttributeError):
        pass

    if not angle:
        angle = fallback_angle
    if mood not in VALID_MOODS:
        mood = DEFAULT_MOOD
    if not reason:
        reason = fallback_reason
    return angle, mood, reason


def generate_angle(
    topic: Topic,
    memory: list[MemoryRecord],
    llm: LLMProvider,
    *,
    rng: random.Random | None = None,
) -> SampledAngle:
    sub_concept, approach, entry_point = sample_cell(topic, memory, rng=rng)

    system = (
        "You write specific, concrete content angles for a single Instagram post — "
        "never generic restatements of the sub-concept. You also tag the emotional mood "
        'of the angle as exactly one of "wisdom", "bold", or "celebratory": wisdom for '
        "reflective/analytical angles, bold for declarative/confident ones, celebratory "
        "for milestone/win angles. And you write a one-line reason (said to the reader "
        "as a quick pitch, e.g. \"a personal story lands this best\") for why this "
        "approach fits the angle.\n"
        "Respond with ONLY JSON, no markdown fence: "
        '{"angle": "...", "mood": "...", "reason": "..."}'
    )
    prompt = (
        f"Topic: {topic.name}\n"
        f"Sub-concept: {sub_concept}\n"
        f"Approach: {approach.value}\n"
        f"Entry point: {entry_point.value}\n"
        f"Knowledge hints: {', '.join(topic.knowledge_hints) or 'none'}"
    )

    raw = llm.complete(tier="cheap", system=system, prompt=prompt, max_tokens=250)
    angle_text, mood, reason = _parse_angle_response(
        raw,
        fallback_angle=sub_concept,
        fallback_reason=f"a {approach.value.replace('_', ' ')} take on {sub_concept}",
    )

    return SampledAngle(
        sub_concept=sub_concept,
        approach=approach,
        entry_point=entry_point,
        angle=angle_text,
        mood=mood,
        reason=reason,
        fingerprint=_fingerprint(topic.id, sub_concept, approach),
    )
