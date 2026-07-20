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
        topic_id="mindset-self-doubt",
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
        topic_id="mindset-self-doubt",
        topics_by_id=topics_by_id,
        angle="the inner critic vs. the intuition that actually protects you",
        approach=Approach.STORY,
        mood="wisdom",
        format=Format.CAROUSEL,
        brand_kit=WGS_BRAND_KIT,
        memory=[],
    )
    assert result.brief.brand_voice_samples == WGS_BRAND_KIT.voice_samples.poetic
    # cover + 3 body (teaching) + closing + conversation = 6, fixed regardless
    # of approach as of logbook #39 round 8 (was 5, teaching-conditional, in
    # round 7)
    assert result.brief.slide_count == 6
    assert result.masthead == "WGS — MINDSET NO. 01"


def test_build_brief_carousel_slide_count_is_6_regardless_of_approach():
    """logbook #39 round 8: body slide count fixed at 3 for every carousel
    approach, so the old teaching-vs-non-teaching slide_count split (5 vs 4)
    collapsed to a flat 6. The body *role* (carousel_body_teaching vs
    carousel_body) still varies by approach -- that's slide_roles_for's job,
    not this count."""
    topics_by_id = get_topics_by_id()
    result = build_brief(
        topic_id="mindset-self-doubt",
        topics_by_id=topics_by_id,
        angle="what confident women do differently when doubt shows up",
        approach=Approach.QUESTION_REFLECTION,
        mood="wisdom",
        format=Format.CAROUSEL,
        brand_kit=WGS_BRAND_KIT,
        memory=[],
    )
    # question_reflection isn't in TEACHING_BODY_APPROACHES, but slide count is
    # fixed at 6 for carousel regardless (round 8) -- same as the teaching case.
    assert result.brief.slide_count == 6


def test_build_brief_resolves_direct_register_for_educational_approach():
    topics_by_id = get_topics_by_id()
    result = build_brief(
        topic_id="career-pay-scale",
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
    assert result.brief.requires_citation is True  # career-pay-scale requires citation


def test_build_brief_masthead_counts_only_exported_same_category():
    topics_by_id = get_topics_by_id()
    memory = [
        _memory_record("Mindset", "exported"),
        _memory_record("Mindset", "exported"),
        _memory_record("Mindset", "draft"),
        _memory_record("Career", "exported"),
    ]
    result = build_brief(
        topic_id="mindset-boundaries",
        topics_by_id=topics_by_id,
        angle="boundaries as information, not punishment",
        approach=Approach.FRAMEWORK,
        mood="wisdom",
        format=Format.CAROUSEL,
        brand_kit=WGS_BRAND_KIT,
        memory=memory,
    )
    assert result.masthead == "WGS — MINDSET NO. 03"


def test_build_brief_hero_image_prompt_uses_visual_subject_not_raw_angle():
    topics_by_id = get_topics_by_id()
    long_angle = (
        "The 3-word reframe when they say 'that's too high': instead of "
        "defending your number, pause and say 'I'm worth it' — a whole "
        "paragraph an image model can't visually translate."
    )
    result = build_brief(
        topic_id="career-pay-scale",
        topics_by_id=topics_by_id,
        angle=long_angle,
        approach=Approach.FRAMEWORK,
        mood="bold",
        format=Format.CAROUSEL,
        brand_kit=WGS_BRAND_KIT,
        memory=[],
        visual_subject="a hand pausing over a phone before hitting send on a salary counteroffer",
    )
    assert (
        result.brief.hero_image_prompt
        == "Abstract, editorial, textural image of a hand pausing over a phone before "
        "hitting send on a salary counteroffer, no literal faces or text, bold mood."
    )
    assert long_angle not in result.brief.hero_image_prompt


def test_build_brief_hero_image_prompt_falls_back_to_angle_when_no_visual_subject():
    topics_by_id = get_topics_by_id()
    result = build_brief(
        topic_id="career-pay-scale",
        topics_by_id=topics_by_id,
        angle="the numbers you need before you ask",
        approach=Approach.FRAMEWORK,
        mood="bold",
        format=Format.CAROUSEL,
        brand_kit=WGS_BRAND_KIT,
        memory=[],
    )
    assert result.brief.hero_image_prompt == (
        "Abstract, editorial, textural image of the numbers you need before you ask, "
        "no literal faces or text, bold mood."
    )


def test_build_brief_hero_image_prompt_does_not_add_quote_wrapping():
    topics_by_id = get_topics_by_id()
    subject = "a woman's hand hesitating over 'send'"
    result = build_brief(
        topic_id="career-pay-scale",
        topics_by_id=topics_by_id,
        angle="a",
        approach=Approach.FRAMEWORK,
        mood="bold",
        format=Format.CAROUSEL,
        brand_kit=WGS_BRAND_KIT,
        memory=[],
        visual_subject=subject,
    )
    # the subject's own apostrophes/quotes pass through untouched — no extra layer
    # of manually-added quote characters wrapped around the whole subject
    assert result.brief.hero_image_prompt == (
        f"Abstract, editorial, textural image of {subject}, no literal faces or text, bold mood."
    )


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
