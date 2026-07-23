from datetime import date, datetime, timezone

from app.engine.brief_builder import build_brief
from app.engine.generator import slide_roles_for
from app.engine.validator import validate_post
from app.models.brief import ContentBrief, Source
from app.models.enums import Approach, Format
from app.models.memory import MemoryRecord
from app.models.post import BodySlide, CoverSlide, GeneratedPost, StatSlide
from app.taxonomy.loader import get_topics_by_id
from app.taxonomy.wgs_brand_kit import WGS_BRAND_KIT


def _brief(topic_id="mindset-self-doubt", approach=Approach.STORY, format=Format.CAROUSEL):
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


# STORY (this file's default approach) is in TEACHING_BODY_APPROACHES, so its
# three body slots are carousel_body_teaching (31-55 words tolerant), not
# carousel_body (9-22) -- a single word count can't satisfy both that floor
# and carousel_closing/carousel_conversation's much lower ceilings at once, so
# _post() sizes each slide's placeholder text to the role real
# slide_roles_for(brief) actually assigns at that position, not one repeated
# string.
_TEACHING_BODY_TEXT = (
    "This is a realistic enough test statement",
    "that has enough words to satisfy the teaching body role's much higher "
    "floor, since a carousel_body_teaching slide needs closer to two full "
    "sentences of real content rather than one short line",
)
_DEFAULT_TEXT = (
    "This is a realistic enough test statement",
    "that has enough words to satisfy every role's minimum range",
)


def _post(n_slides=6, heading=None, body=None, brief=None) -> GeneratedPost:
    roles = slide_roles_for(brief if brief is not None else _brief())
    slides = []
    for i in range(n_slides):
        role = roles[i] if i < len(roles) else "carousel_body"
        default_heading, default_body = _TEACHING_BODY_TEXT if role == "carousel_body_teaching" else _DEFAULT_TEXT
        slides.append(
            BodySlide(
                statement_pre=heading if heading is not None else default_heading,
                statement_script="",
                statement_post=body if body is not None else default_body,
            )
        )
    return GeneratedPost(slides=slides, caption="a caption", hashtags=["#a"])


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
    assert any("expected 6 slide" in e for e in result.errors)


def test_validate_post_flags_word_limit():
    long_body = " ".join(["word"] * 40)
    post = _post(body=long_body)
    result = validate_post(_brief(), WGS_BRAND_KIT, post, [], "fp-4")
    assert not result.passed
    assert any("exceeds max_words_per_slide" in e for e in result.errors)


def test_validate_post_passes_citation_required_topic_grounded_by_knowledge_hints():
    """Logbook #14: career-pay-scale requires_citation, but build_brief()
    now threads topic.knowledge_hints into the brief — sources stays empty by
    design (taxonomy topics never carry real Source objects) and that's correct,
    not a validation failure."""
    brief = _brief(
        topic_id="career-pay-scale",
        approach=Approach.EDUCATIONAL,
        format=Format.SINGLE_IMAGE,
    )
    assert brief.sources == []
    assert brief.knowledge_hints
    result = validate_post(brief, WGS_BRAND_KIT, _post(n_slides=1), [], "fp-5")
    assert result.passed
    assert not any("requires_citation" in e for e in result.errors)


def test_validate_post_flags_citation_required_with_neither_sources_nor_hints():
    """The real bug: a citation-required brief with no grounding at all —
    e.g. a paste-link brief that failed to pin a Source, or a taxonomy brief
    that somehow bypassed the startup loader guard requiring knowledge_hints."""
    brief = ContentBrief(
        topic_id="paste-link:abc123",
        topic_name="A Test Article",
        angle="an angle",
        approach=Approach.STAT_RESEARCH,
        goal="inform",
        format=Format.SINGLE_IMAGE,
        slide_count=1,
        tone=["warm"],
        brand_voice_samples=["a"],
        requires_citation=True,
        sources=[],
        knowledge_hints=[],
        hero_image_prompt="a prompt",
    )
    result = validate_post(brief, WGS_BRAND_KIT, _post(n_slides=1), [], "fp-5")
    assert not result.passed
    assert any("neither sources nor knowledge_hints" in e for e in result.errors)


def test_validate_post_passes_citation_required_with_real_sources():
    """The paste-link flow's own success case: real pinned Source objects,
    no knowledge_hints — still correctly grounded, still passes."""
    brief = ContentBrief(
        topic_id="paste-link:abc123",
        topic_name="A Test Article",
        angle="an angle",
        approach=Approach.STAT_RESEARCH,
        goal="inform",
        format=Format.SINGLE_IMAGE,
        slide_count=1,
        tone=["warm"],
        brand_voice_samples=["a"],
        requires_citation=True,
        sources=[
            Source(
                title="A Test Article",
                url="https://example.com/a",
                excerpt="a citable excerpt",
                retrieved_at=datetime.now(timezone.utc),
            )
        ],
        knowledge_hints=[],
        hero_image_prompt="a prompt",
    )
    result = validate_post(brief, WGS_BRAND_KIT, _post(n_slides=1), [], "fp-5")
    assert result.passed
    assert not any("requires_citation" in e for e in result.errors)


def test_validate_post_flags_slide_below_its_template_word_floor():
    """carousel_body's real per-template floor (10-20, tolerant 9-22) -- a
    slide this short left large, unintentional-looking empty space on a real
    Satori render (docs/logbook.md), which the old flat cap (max-only, no
    floor) could never catch. QUESTION_REFLECTION isn't in
    TEACHING_BODY_APPROACHES, so its body slots are plain carousel_body, not
    carousel_body_teaching -- unlike this file's default STORY approach."""
    brief = _brief(approach=Approach.QUESTION_REFLECTION)
    assert slide_roles_for(brief)[1] == "carousel_body"
    post = _post(brief=brief)
    post.slides[1] = BodySlide(statement_pre="Too short", statement_script="", statement_post="")
    result = validate_post(brief, WGS_BRAND_KIT, post, [], "fp-7")
    assert not result.passed
    assert any("below the 9-word floor" in e for e in result.errors)


def test_validate_post_flags_slide_above_its_template_word_ceiling():
    """carousel_closing's real per-template ceiling (10-20, tolerant 9-22)."""
    post = _post()
    long_takeaway = " ".join(["word"] * 30)
    post.slides[4] = BodySlide(statement_pre=long_takeaway, statement_script="", statement_post="")
    result = validate_post(_brief(), WGS_BRAND_KIT, post, [], "fp-8")
    assert not result.passed
    assert any("exceeds the 22-word ceiling" in e for e in result.errors)


# _post()'s default filler (17 words combined) satisfies legacy's ranges (the
# smallest of which floors at 9-10) but not direct-write's wider cover/closing
# floors (18 and 21 respectively) -- these two fillers isolate "the slide
# under test" from "the other slide direct-write also widens", so a test on
# one doesn't spuriously fail on the other's now-too-short default filler.
_DIRECT_WRITE_COVER_FILLER = " ".join(["word"] * 20)  # clears the (18, 50) floor
_DIRECT_WRITE_CLOSING_FILLER = " ".join(["word"] * 22)  # clears the (21, 61) floor


def test_validate_post_direct_write_closing_allows_a_real_2_to_4_sentence_build():
    """Task '#19': carousel direct-write's closing is a real 2-4 sentence build,
    not legacy's one-line takeaway -- a 30-word closing fails against legacy's
    ceiling (previous test, unchanged) but must pass once carousel_writer=
    "direct_write" tells validate_post to use the wider, direct-write-only
    range instead (_CAROUSEL_DIRECT_CLOSING_WORD_RANGE, tolerant ceiling 61)."""
    post = _post()
    post.slides[0] = BodySlide(statement_pre=_DIRECT_WRITE_COVER_FILLER, statement_script="", statement_post="")
    thirty_word_closing = " ".join(["word"] * 30)
    post.slides[4] = BodySlide(statement_pre=thirty_word_closing, statement_script="", statement_post="")
    result = validate_post(_brief(), WGS_BRAND_KIT, post, [], "fp-8b", carousel_writer="direct_write")
    assert result.passed
    assert result.errors == []


def test_validate_post_direct_write_closing_still_flags_genuine_overflow():
    """The wider direct-write range still has a real ceiling -- it isn't
    unlimited just because it's wider than legacy's."""
    post = _post()
    post.slides[0] = BodySlide(statement_pre=_DIRECT_WRITE_COVER_FILLER, statement_script="", statement_post="")
    way_too_long_closing = " ".join(["word"] * 80)
    post.slides[4] = BodySlide(statement_pre=way_too_long_closing, statement_script="", statement_post="")
    result = validate_post(_brief(), WGS_BRAND_KIT, post, [], "fp-8c", carousel_writer="direct_write")
    assert not result.passed
    assert any("exceeds the" in e and "ceiling" in e for e in result.errors)


def test_validate_post_direct_write_cover_gets_its_own_wider_range():
    """Task '#19': carousel_cover has no entry in _WORD_RANGE_FOR_ROLE at all
    (legacy's one-word headline + one-line kicker never needed one), so it
    falls back to the flat max_words_per_slide cap (tolerant ceiling 33) by
    default. Direct-write's real cover_body paragraph needs more room than
    that -- a 40-word cover must pass under carousel_writer="direct_write"
    (tolerant ceiling 50) but would fail the old flat cap if it applied."""
    brief = _brief()
    cover_text = " ".join(["word"] * 40)
    post = _post(brief=brief)
    post.slides[0] = CoverSlide(
        headline_word=cover_text, script_word="", kicker="", cover_body=""
    )
    post.slides[4] = BodySlide(statement_pre=_DIRECT_WRITE_CLOSING_FILLER, statement_script="", statement_post="")
    result = validate_post(brief, WGS_BRAND_KIT, post, [], "fp-8d", carousel_writer="direct_write")
    assert result.passed
    assert result.errors == []

    legacy_result = validate_post(brief, WGS_BRAND_KIT, post, [], "fp-8e", carousel_writer="legacy")
    assert not legacy_result.passed
    assert any("exceeds max_words_per_slide" in e for e in legacy_result.errors)


def _single_stat_post(number="42%", supporting_line=None) -> GeneratedPost:
    if supporting_line is None:
        supporting_line = (
            "One punchy line was never going to be enough content to fill "
            "this slide comfortably on its own"
        )
    return GeneratedPost(
        slides=[StatSlide(kicker="RESEARCH", number=number, supporting_line=supporting_line)],
        caption="a caption",
        hashtags=["#a"],
    )


def test_validate_post_passes_single_stat_with_short_number_field():
    brief = _brief(approach=Approach.STAT_RESEARCH, format=Format.SINGLE_IMAGE)
    result = validate_post(brief, WGS_BRAND_KIT, _single_stat_post(), [], "fp-9")
    assert result.passed
    assert result.errors == []


def test_validate_post_flags_single_stat_number_field_overflow():
    """The real production bug (docs/logbook.md): a refine step put an
    ungrounded generalization ("Women face a tighter error margin", 5 words)
    in the `number` field, which renders at 200px with no wrap guard and
    overflowed the entire canvas on a real Satori render. Previously
    unbounded by anything -- this is the regression test for that fix."""
    brief = _brief(approach=Approach.STAT_RESEARCH, format=Format.SINGLE_IMAGE)
    post = _single_stat_post(number="Women face a tighter error margin")
    result = validate_post(brief, WGS_BRAND_KIT, post, [], "fp-10")
    assert not result.passed
    assert any("number field has 6 word(s)" in e for e in result.errors)


def test_validate_post_flags_single_stat_supporting_line_too_short():
    brief = _brief(approach=Approach.STAT_RESEARCH, format=Format.SINGLE_IMAGE)
    post = _single_stat_post(supporting_line="too short")
    result = validate_post(brief, WGS_BRAND_KIT, post, [], "fp-11")
    assert not result.passed
    assert any("supporting_line has 2 words" in e for e in result.errors)


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
