"""Angle engine — samples one (sub-concept x approach x entry-point) cell from a Topic
and the two global lists, then asks the cheap tier to write the specific angle sentence
and tag the post's mood in the same call (blueprint Section 5)."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from typing import Literal

from app.models.enums import Approach, EntryPoint, Format
from app.models.memory import MemoryRecord
from app.models.topic import Topic
from app.providers.llm import LLMProvider, strip_json_fence
from app.taxonomy.approaches import (
    APPROACHES,
    CAROUSEL_V1_APPROACHES,
    SINGLE_IMAGE_QUOTE_APPROACHES,
    SINGLE_IMAGE_SAFE_APPROACHES,
    SINGLE_IMAGE_STAT_APPROACHES,
)
from app.taxonomy.entry_points import ENTRY_POINTS

SingleImageStyle = Literal["quote", "stat"]

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
    visual_subject: str
    fingerprint: str


def _fingerprint(topic_id: str, sub_concept: str, approach: Approach) -> str:
    return f"{topic_id}:{sub_concept}:{approach.value}"


def sample_cell(
    topic: Topic,
    memory: list[MemoryRecord],
    *,
    format: Format | None = None,
    single_image_style: SingleImageStyle | None = None,
    rng: random.Random | None = None,
) -> tuple[str, Approach, EntryPoint]:
    """Pick one (sub-concept, approach, entry-point) cell, excluding combinations whose
    topic+sub-concept+approach fingerprint already appears in this topic's memory. Falls
    back to the full pool once every combination for this topic has been used.

    `format` narrows which approaches are eligible: single_image resolves to exactly one
    slide, which some approaches structurally can't fit (see
    taxonomy/approaches.py:SINGLE_IMAGE_SAFE_APPROACHES). `format=None` (the daily-picks
    pitch path, where no format has been chosen yet) samples unrestricted, same as
    carousel.

    `single_image_style` further narrows the single_image pool to just the quote-style
    or stat-style half (logbook #28) when she's chosen "Poetic Quote"/"Quick Stat" up
    front — ignored unless format is single_image; leaving it unset preserves today's
    behavior of sampling from the full 4-approach safe pool.

    `format=Format.CAROUSEL` restricts the pool to CAROUSEL_V1_APPROACHES (story,
    question_reflection) — the carousel-only "v1" content-voice experiment (logbook
    #39). Experimental, pending real-output review. single_image's behavior above is
    completely unaffected by this branch; `format=None` (the daily-picks pitch path,
    where no format has been chosen yet) still samples the full, unrestricted pool."""
    rng = rng or random.Random()
    used_fingerprints = {r.fingerprint for r in memory if r.topic_id == topic.id}

    if format == Format.SINGLE_IMAGE:
        if single_image_style == "quote":
            allowed_approaches = SINGLE_IMAGE_QUOTE_APPROACHES
        elif single_image_style == "stat":
            allowed_approaches = SINGLE_IMAGE_STAT_APPROACHES
        else:
            allowed_approaches = SINGLE_IMAGE_SAFE_APPROACHES
    elif format == Format.CAROUSEL:
        allowed_approaches = CAROUSEL_V1_APPROACHES
    else:
        allowed_approaches = APPROACHES

    candidates = [
        (sub, Approach(a), EntryPoint(e))
        for sub in topic.seed_angles
        for a in allowed_approaches
        for e in ENTRY_POINTS
    ]
    unused = [c for c in candidates if _fingerprint(topic.id, c[0], c[1]) not in used_fingerprints]
    pool = unused or candidates
    return rng.choice(pool)


def _parse_angle_response(
    raw: str,
    *,
    fallback_angle: str,
    fallback_reason: str,
    fallback_visual_subject: str,
) -> tuple[str, str, str, str]:
    angle, mood, reason, visual_subject = "", "", "", ""
    try:
        data = json.loads(strip_json_fence(raw))
        angle = str(data.get("angle") or "").strip()
        mood = str(data.get("mood") or "").strip().lower()
        reason = str(data.get("reason") or "").strip()
        visual_subject = str(data.get("visual_subject") or "").strip()
    except (json.JSONDecodeError, AttributeError):
        pass

    if not angle:
        angle = fallback_angle
    if mood not in VALID_MOODS:
        mood = DEFAULT_MOOD
    if not reason:
        reason = fallback_reason
    if not visual_subject:
        visual_subject = fallback_visual_subject
    return angle, mood, reason, visual_subject


def generate_angle(
    topic: Topic,
    memory: list[MemoryRecord],
    llm: LLMProvider,
    *,
    format: Format | None = None,
    single_image_style: SingleImageStyle | None = None,
    rng: random.Random | None = None,
) -> SampledAngle:
    sub_concept, approach, entry_point = sample_cell(
        topic, memory, format=format, single_image_style=single_image_style, rng=rng
    )

    system = (
        "You write specific, concrete content angles for a single Instagram post — "
        "never generic restatements of the sub-concept. You also tag the emotional mood "
        'of the angle as exactly one of "wisdom", "bold", or "celebratory": wisdom for '
        "reflective/analytical angles, bold for declarative/confident ones, celebratory "
        "for milestone/win angles. And you write a one-line reason (said to the reader "
        "as a quick pitch, e.g. \"a personal story lands this best\") for why this "
        "approach fits the angle.\n"
        "You also write visual_subject: 5-15 words naming ONE concrete image, object, "
        "or scene genuinely tied to THIS specific topic and angle — something a "
        "photographer could actually go photograph (e.g. \"a hand hovering over "
        "send on a half-written text message\", \"a cluttered desk with an unsigned "
        "resignation letter\"). Never an abstract mood word like \"transformation\", "
        '"growth", or "balance", and never a generic stock-photo trope like a '
        "staircase or a winding path — it must be recognizably specific to this "
        "angle, not swappable with any other post's.\n"
        "Respond with ONLY JSON, no markdown fence: "
        '{"angle": "...", "mood": "...", "reason": "...", "visual_subject": "..."}'
    )
    prompt = (
        f"Topic: {topic.name}\n"
        f"Sub-concept: {sub_concept}\n"
        f"Approach: {approach.value}\n"
        f"Entry point: {entry_point.value}\n"
        f"Knowledge hints: {', '.join(topic.knowledge_hints) or 'none'}"
    )

    raw = llm.complete(tier="cheap", system=system, prompt=prompt, max_tokens=300)
    angle_text, mood, reason, visual_subject = _parse_angle_response(
        raw,
        fallback_angle=sub_concept,
        fallback_reason=f"a {approach.value.replace('_', ' ')} take on {sub_concept}",
        fallback_visual_subject=sub_concept,
    )

    return SampledAngle(
        sub_concept=sub_concept,
        approach=approach,
        entry_point=entry_point,
        angle=angle_text,
        mood=mood,
        reason=reason,
        visual_subject=visual_subject,
        fingerprint=_fingerprint(topic.id, sub_concept, approach),
    )


@dataclass
class CarouselContext:
    """Context for the carousel direct-write port (docs/logbook.md #43) to pick
    its own anchor from, rather than being handed one dictated sub-concept/
    approach/entry-point cell. Every field here is context to inform the
    model's choice, never a requirement it must satisfy."""

    category: str
    seed_angles: list[str]
    # Empty unless topic.requires_citation -- knowledge_hints exists specifically
    # to ground citation-required topics (logbook #14); handing it to a
    # non-citation topic would be dead weight the prompt never needs.
    knowledge_hints: list[str]
    # This topic's own previously-used anchors, most recent first as stored --
    # a caller-facing avoid-list, the same purpose recent_anchors already
    # serves in the isolated POC (app/poc/FINDINGS.md #1), now sourced from
    # real persisted memory instead of a hand-fed test-harness list.
    recent_anchors: list[str]


def assemble_carousel_context(topic: Topic, memory: list[MemoryRecord]) -> CarouselContext:
    """Carousel-only, pure Python, no LLM call -- replaces sample_cell() and
    generate_angle() for the direct-write port. Pulls topic.primary_category,
    every one of topic.seed_angles (not one sampled sub-concept),
    topic.knowledge_hints when citation-required, and this topic's own
    recorded anchors from memory. Deliberately reads nothing about approach or
    entry_point -- those concepts don't exist on this path at all; they stay
    used only by sample_cell/generate_angle, single_image's unchanged path."""
    recent_anchors = [r.anchor for r in memory if r.topic_id == topic.id and r.anchor]
    return CarouselContext(
        category=topic.primary_category,
        seed_angles=list(topic.seed_angles),
        knowledge_hints=list(topic.knowledge_hints) if topic.requires_citation else [],
        recent_anchors=recent_anchors,
    )
