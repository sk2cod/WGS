from datetime import date

import pytest

from app.engine.brief_builder import build_brief
from app.models.enums import Approach, Format
from app.models.memory import MemoryRecord
from app.taxonomy.loader import get_topics_by_id
from app.taxonomy.wgs_brand_kit import WGS_BRAND_KIT


def _memory_record(category: str, status: str) -> MemoryRecord:
    return MemoryRecord(
        id=f"m-{category}-{status}",
        date=date(2026, 1, 1),
        topic_id="mindset-reframing-self-doubt",
        category=category,
        angle="some angle",
        approach=Approach.STORY,
        format=Format.CAROUSEL,
        mood="wisdom",
        hook="hook",
        fingerprint="fp",
        status=status,
    )


def test_build_brief_resolves_poetic_register_for_story_approach():
    topics_by_id = get_topics_by_id()
    result = build_brief(
        topic_id="mindset-reframing-self-doubt",
        topics_by_id=topics_by_id,
        angle="the inner critic vs. the intuition that actually protects you",
        approach=Approach.STORY,
        mood="wisdom",
        format=Format.CAROUSEL,
        brand_kit=WGS_BRAND_KIT,
        memory=[],
    )
    assert result.brief.brand_voice_samples == WGS_BRAND_KIT.voice_samples.poetic
    assert result.brief.slide_count == 3
    assert result.masthead == "WGS — MINDSET NO. 01"


def test_build_brief_resolves_direct_register_for_educational_approach():
    topics_by_id = get_topics_by_id()
    result = build_brief(
        topic_id="career-salary-negotiation",
        topics_by_id=topics_by_id,
        angle="the numbers you need before you ask",
        approach=Approach.EDUCATIONAL,
        mood="bold",
        format=Format.SINGLE_IMAGE,
        brand_kit=WGS_BRAND_KIT,
        memory=[],
    )
    assert result.brief.brand_voice_samples == WGS_BRAND_KIT.voice_samples.direct
    assert result.brief.slide_count == 1
    assert result.brief.requires_citation is True  # career-salary-negotiation requires citation


def test_build_brief_masthead_counts_only_exported_same_category():
    topics_by_id = get_topics_by_id()
    memory = [
        _memory_record("Mindset", "exported"),
        _memory_record("Mindset", "exported"),
        _memory_record("Mindset", "draft"),
        _memory_record("Career", "exported"),
    ]
    result = build_brief(
        topic_id="mindset-boundaries-without-guilt",
        topics_by_id=topics_by_id,
        angle="boundaries as information, not punishment",
        approach=Approach.FRAMEWORK,
        mood="wisdom",
        format=Format.CAROUSEL,
        brand_kit=WGS_BRAND_KIT,
        memory=memory,
    )
    assert result.masthead == "WGS — MINDSET NO. 03"


def test_build_brief_raises_on_unknown_topic():
    with pytest.raises(KeyError):
        build_brief(
            topic_id="does-not-exist",
            topics_by_id=get_topics_by_id(),
            angle="n/a",
            approach=Approach.STORY,
            mood="wisdom",
            format=Format.CAROUSEL,
            brand_kit=WGS_BRAND_KIT,
            memory=[],
        )
