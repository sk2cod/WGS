from pydantic import BaseModel

from app.models.brand_kit import BrandKit
from app.models.brief import ContentBrief
from app.models.enums import Approach, Format
from app.models.memory import MemoryRecord, next_masthead_number
from app.models.topic import Topic
from app.taxonomy.approaches import TEACHING_BODY_APPROACHES
from app.taxonomy.voice_register import APPROACH_REGISTER


def _default_slide_count(format: Format, approach: Approach) -> int:
    """Carousels default to 5 slides (cover + 2 teaching body + closing +
    conversation) for approaches that need real teaching room, 4 otherwise
    (cover + 1 body + closing + conversation) — see
    taxonomy/approaches.py:TEACHING_BODY_APPROACHES. The +1 vs. the original
    4/3 is carousel_conversation (logbook #39, round 7) — the first structural
    change in the v1 line of work, appended after closing for every carousel
    brief regardless of approach."""
    if format == Format.SINGLE_IMAGE:
        return 1
    return 5 if approach.value in TEACHING_BODY_APPROACHES else 4


def _hero_image_prompt(subject: str, mood: str) -> str:
    """`subject` should be a concrete visual_subject (angle_engine), not a raw
    multi-sentence angle — an image model can't visually translate an argument,
    only a scene. No manual quote-wrapping around free text either: `subject`
    may itself contain apostrophes, and nesting unescaped text inside quote
    characters is fragile."""
    return f"Abstract, editorial, textural image of {subject}, no literal faces or text, {mood} mood."


class BriefResult(BaseModel):
    """`ContentBrief` plus the masthead string computed for it. The masthead itself
    isn't part of the ContentBrief contract (Section 6) — it's a render-time label
    (Section 8) — so it travels alongside the brief rather than inside it."""

    brief: ContentBrief
    masthead: str


def build_brief(
    *,
    topic_id: str,
    topics_by_id: dict[str, Topic],
    angle: str,
    approach: Approach,
    mood: str,
    format: Format,
    brand_kit: BrandKit,
    memory: list[MemoryRecord],
    goal: str = "educate",
    slide_count: int | None = None,
    visual_subject: str | None = None,
) -> BriefResult:
    """Assemble a ContentBrief for one post: resolve which BrandKit voice register
    (poetic or direct) this approach draws from, inject only that list, and compute
    the masthead number from content memory — everything downstream reads from here."""
    topic = topics_by_id.get(topic_id)
    if topic is None:
        raise KeyError(f"Unknown topic_id: {topic_id!r}")

    register = APPROACH_REGISTER[approach.value]
    brand_voice_samples = list(getattr(brand_kit.voice_samples, register))

    resolved_slide_count = (
        slide_count if slide_count is not None else _default_slide_count(format, approach)
    )

    brief = ContentBrief(
        topic_id=topic.id,
        topic_name=topic.name,
        angle=angle,
        approach=approach,
        goal=goal,
        mood=mood,
        format=format,
        slide_count=resolved_slide_count,
        tone=topic.tone_defaults or brand_kit.default_tone,
        brand_voice_samples=brand_voice_samples,
        signature_cta=brand_kit.signature_cta,
        requires_citation=topic.requires_citation,
        sensitivity=topic.sensitivity,
        sources=[],
        knowledge_hints=topic.knowledge_hints,
        hero_image_prompt=_hero_image_prompt(visual_subject or angle, mood),
    )

    masthead = next_masthead_number(topic.primary_category, memory)

    return BriefResult(brief=brief, masthead=f"{brand_kit.masthead_short} — {masthead}")
