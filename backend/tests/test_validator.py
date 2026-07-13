from datetime import date

from app.engine.brief_builder import build_brief
from app.engine.validator import validate_post
from app.models.enums import Approach, Format
from app.models.memory import MemoryRecord
from app.models.post import BodySlide, GeneratedPost
from app.taxonomy.loader import get_topics_by_id
from app.taxonomy.wgs_brand_kit import WGS_BRAND_KIT


def _brief(topic_id="mindset-reframing-self-doubt", approach=Approach.STORY, format=Format.CAROUSEL):
    return build_brief(
        topic_id=topic_id,
        topics_by_id=get_topics_by_id(),
        angle="a",
        approach=approach,
        mood="wisdom",
        format=format,
        brand_kit=WGS_BRAND_KIT,
        memory=[],
    ).brief


def _post(n_slides=4, heading="Pause", body="short body") -> GeneratedPost:
    return GeneratedPost(
        slides=[
            BodySlide(statement_pre=heading, statement_script="", statement_post=body)
            for _ in range(n_slides)
        ],
        caption="a caption",
        hashtags=["#a"],
    )


def test_validate_post_passes_clean_post():
    result = validate_post(_brief(), WGS_BRAND_KIT, _post(), [], "fp-1")
    assert result.passed
    assert result.errors == []


def test_validate_post_flags_forbidden_phrase():
    post = _post(heading="hustle-mindset language", body="short body")
    result = validate_post(_brief(), WGS_BRAND_KIT, post, [], "fp-2")
    assert not result.passed
    assert any("hustle-mindset language" in e for e in result.errors)


def test_validate_post_flags_wrong_slide_count():
    result = validate_post(_brief(), WGS_BRAND_KIT, _post(n_slides=2), [], "fp-3")
    assert not result.passed
    assert any("expected 4 slide" in e for e in result.errors)


def test_validate_post_flags_word_limit():
    long_body = " ".join(["word"] * 40)
    post = _post(body=long_body)
    result = validate_post(_brief(), WGS_BRAND_KIT, post, [], "fp-4")
    assert not result.passed
    assert any("exceeds max_words_per_slide" in e for e in result.errors)


def test_validate_post_flags_missing_citation():
    brief = _brief(
        topic_id="career-salary-negotiation",
        approach=Approach.EDUCATIONAL,
        format=Format.SINGLE_IMAGE,
    )
    result = validate_post(brief, WGS_BRAND_KIT, _post(n_slides=1), [], "fp-5")
    assert not result.passed
    assert any("requires_citation" in e for e in result.errors)


def test_validate_post_flags_repetition():
    brief = _brief()
    memory = [
        MemoryRecord(
            id="m1",
            date=date(2026, 1, 1),
            topic_id=brief.topic_id,
            category="Mindset",
            angle="a",
            approach=Approach.STORY,
            format=Format.CAROUSEL,
            mood="wisdom",
            hook="h",
            fingerprint="fp-6",
            status="exported",
        )
    ]
    result = validate_post(brief, WGS_BRAND_KIT, _post(), memory, "fp-6")
    assert not result.passed
    assert any("already exists" in e for e in result.errors)
