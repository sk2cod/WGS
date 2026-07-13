from datetime import date, datetime

import pytest
from pydantic import ValidationError

from app.models.brief import ContentBrief, Source
from app.models.enums import Approach, Format, Sensitivity
from app.models.memory import MemoryRecord, next_masthead_number
from app.models.topic import Topic
from app.taxonomy.wgs_brand_kit import WGS_BRAND_KIT


def test_brand_kit_fixture_loads():
    assert WGS_BRAND_KIT.masthead_short == "WGS"
    assert len(WGS_BRAND_KIT.voice_samples.poetic) == 5
    assert len(WGS_BRAND_KIT.voice_samples.direct) == 5
    assert set(WGS_BRAND_KIT.mood_palettes) == {"wisdom", "bold", "celebratory"}


def test_topic_requires_categories_and_formats():
    topic = Topic(
        id="t1",
        name="Test Topic",
        categories=["Mindset"],
        primary_category="Mindset",
        tone_defaults=["warm"],
        suitable_formats=[Format.CAROUSEL],
        seed_angles=["angle one", "angle two", "angle three"],
    )
    assert topic.sensitivity == Sensitivity.NORMAL
    assert topic.requires_citation is False

    with pytest.raises(ValidationError):
        Topic(
            id="t2",
            name="Bad Topic",
            categories=["Mindset"],
            primary_category="Mindset",
            tone_defaults=["warm"],
            suitable_formats=["not_a_format"],
            seed_angles=["a"],
        )


def test_content_brief_round_trips():
    brief = ContentBrief(
        topic_id="t1",
        topic_name="Test Topic",
        angle="a relatable moment",
        approach=Approach.STORY,
        goal="reflect",
        mood="wisdom",
        format=Format.CAROUSEL,
        slide_count=3,
        tone=["warm"],
        brand_voice_samples=["sample line"],
        signature_cta="Follow along.",
        requires_citation=False,
        sensitivity=Sensitivity.NORMAL,
        sources=[
            Source(
                title="Some Article",
                author=None,
                url="https://example.com",
                excerpt="citable text",
                retrieved_at=datetime(2026, 1, 1),
            )
        ],
        hero_image_prompt="abstract textures",
    )
    dumped = brief.model_dump()
    assert dumped["approach"] == "story"
    assert ContentBrief.model_validate(dumped) == brief


def test_next_masthead_number_counts_exported_only():
    memory = [
        MemoryRecord(
            id="m1",
            date=date(2026, 1, 1),
            topic_id="t1",
            category="Mindset",
            angle="a",
            approach=Approach.STORY,
            format=Format.CAROUSEL,
            mood="wisdom",
            hook="hook",
            fingerprint="fp1",
            status="exported",
        ),
        MemoryRecord(
            id="m2",
            date=date(2026, 1, 2),
            topic_id="t2",
            category="Mindset",
            angle="b",
            approach=Approach.EDUCATIONAL,
            format=Format.SINGLE_IMAGE,
            mood="bold",
            hook="hook2",
            fingerprint="fp2",
            status="draft",
        ),
        MemoryRecord(
            id="m3",
            date=date(2026, 1, 3),
            topic_id="t3",
            category="Career",
            angle="c",
            approach=Approach.FRAMEWORK,
            format=Format.CAROUSEL,
            mood="celebratory",
            hook="hook3",
            fingerprint="fp3",
            status="exported",
        ),
    ]
    assert next_masthead_number("Mindset", memory) == "MINDSET NO. 02"
    assert next_masthead_number("Career", memory) == "CAREER NO. 02"
    assert next_masthead_number("Wellness", memory) == "WELLNESS NO. 01"
