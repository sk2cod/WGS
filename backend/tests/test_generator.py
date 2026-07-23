import json
from datetime import datetime, timezone

import pytest

from app.engine.brief_builder import build_brief
from app.engine.generator import (
    _parse_carousel_direct_response,
    critique_post,
    draft_post,
    generate_post,
    refine_post,
    regenerate_slide,
    slide_roles_for,
)
from app.models.brief import ContentBrief, Source
from app.models.enums import Approach, Format
from app.models.post import (
    BodySlide,
    BodyTeachingSlide,
    ClosingSlide,
    ConversationSlide,
    CoverSlide,
    GeneratedPost,
    StatSlide,
)
from app.taxonomy.loader import get_topics_by_id
from app.taxonomy.wgs_brand_kit import WGS_BRAND_KIT

# _sample_brief() -> carousel, story approach (a TEACHING_BODY_APPROACHES approach):
# roles = [carousel_cover, carousel_body_teaching, carousel_body_teaching,
#          carousel_body_teaching, carousel_closing, carousel_conversation] --
# 3 body slides (logbook #39 round 8, up from 1-2), conversation (round 7).
_DRAFT_CAROUSEL_JSON = json.dumps(
    {
        "slides": [
            {"headline_word": "PAUSE", "script_word": "first.", "kicker": "Before you react, breathe."},
            {
                "heading": "The inner critic",
                "body": "It shows up as certainty, but it's really just an old habit dressed up as truth.",
            },
            {
                "heading": "The intuition",
                "body": "It's quieter, and it usually shows up as a question rather than a verdict.",
            },
            {
                "heading": "The choice",
                "body": "Every time you notice the difference, choosing gets a little easier.",
            },
            {"takeaway": "You get to decide which one leads."},
            {"question": "Which voice have you been listening to today?"},
        ],
        "caption": "The inner critic isn't always right.",
        "hashtags": ["#selfdoubt", "#growth"],
    }
)


class _QueueLLM:
    def __init__(self, responses):
        self._responses = list(responses)
        self.tiers_called: list[str] = []
        self.prompts: list[str] = []

    def complete(self, *, tier, system, prompt, max_tokens, cache=True):
        self.tiers_called.append(tier)
        self.prompts.append(prompt)
        return self._responses.pop(0)


def _sample_brief():
    return build_brief(
        topic_id="mindset-self-doubt",
        topics_by_id=get_topics_by_id(),
        angle="the inner critic vs. the intuition that actually protects you",
        approach=Approach.STORY,
        mood="wisdom",
        format=Format.CAROUSEL,
        brand_kit=WGS_BRAND_KIT,
        memory=[],
    ).brief


def _non_teaching_brief():
    return build_brief(
        topic_id="mindset-self-doubt",
        topics_by_id=get_topics_by_id(),
        angle="what confident women do differently when doubt shows up",
        approach=Approach.QUESTION_REFLECTION,
        mood="wisdom",
        format=Format.CAROUSEL,
        brand_kit=WGS_BRAND_KIT,
        memory=[],
    ).brief


def _citation_required_brief():
    return build_brief(
        topic_id="career-pay-scale",
        topics_by_id=get_topics_by_id(),
        angle="the numbers you need before you ask",
        approach=Approach.EDUCATIONAL,
        mood="bold",
        format=Format.SINGLE_IMAGE,
        brand_kit=WGS_BRAND_KIT,
        memory=[],
    ).brief


def test_slide_roles_for_teaching_approach_uses_three_body_teaching_slides():
    assert slide_roles_for(_sample_brief()) == [
        "carousel_cover",
        "carousel_body_teaching",
        "carousel_body_teaching",
        "carousel_body_teaching",
        "carousel_closing",
        "carousel_conversation",
    ]


def test_slide_roles_for_non_teaching_approach_uses_three_body_slides():
    assert slide_roles_for(_non_teaching_brief()) == [
        "carousel_cover",
        "carousel_body",
        "carousel_body",
        "carousel_body",
        "carousel_closing",
        "carousel_conversation",
    ]


def test_slide_roles_for_single_image_direct_register_is_stat():
    assert slide_roles_for(_citation_required_brief()) == ["single_stat"]


def test_draft_post_parses_response():
    llm = _QueueLLM([_DRAFT_CAROUSEL_JSON])
    post = draft_post(_sample_brief(), WGS_BRAND_KIT, llm)
    assert len(post.slides) == 6
    assert post.slides[0].template_id == "carousel_cover"
    assert post.slides[1].template_id == "carousel_body_teaching"
    assert post.slides[2].template_id == "carousel_body_teaching"
    assert post.slides[3].template_id == "carousel_body_teaching"
    assert post.slides[4].template_id == "carousel_closing"
    assert post.slides[5].template_id == "carousel_conversation"
    assert post.caption == "The inner critic isn't always right."
    assert llm.tiers_called == ["strong"]


def test_draft_post_fills_closing_slide_from_brand_kit_not_llm():
    """cta/handle moved to the conversation slide in round 8 -- closing only
    ever had takeaway (model-written) and signature (hardcoded, not
    brand_kit-driven) to begin with."""
    llm = _QueueLLM([_DRAFT_CAROUSEL_JSON])
    post = draft_post(_sample_brief(), WGS_BRAND_KIT, llm)
    closing = post.slides[4]
    assert closing.takeaway == "You get to decide which one leads."
    assert closing.signature == "with you,"


def test_draft_post_fills_conversation_slide_fixed_fields_from_defaults_not_llm():
    """label, invite, cta, and handle are all fixed brand copy -- cta/handle
    moved here from the closing slide in round 8, the true last slide."""
    llm = _QueueLLM([_DRAFT_CAROUSEL_JSON])
    post = draft_post(_sample_brief(), WGS_BRAND_KIT, llm)
    conversation = post.slides[5]
    assert conversation.question == "Which voice have you been listening to today?"
    assert conversation.label == "- Conversation for today"
    assert conversation.invite == "I'd love to hear it."
    assert conversation.cta == WGS_BRAND_KIT.signature_cta
    assert conversation.handle == WGS_BRAND_KIT.handle


def test_draft_post_strips_markdown_fence():
    llm = _QueueLLM([f"```json\n{_DRAFT_CAROUSEL_JSON}\n```"])
    post = draft_post(_sample_brief(), WGS_BRAND_KIT, llm)
    assert len(post.slides) == 6


def test_generate_post_runs_draft_critique_refine_when_enabled():
    llm = _QueueLLM([_DRAFT_CAROUSEL_JSON, "no changes needed", _DRAFT_CAROUSEL_JSON])
    post = generate_post(_sample_brief(), WGS_BRAND_KIT, llm, enable_critique=True)
    assert llm.tiers_called == ["strong", "strong", "strong"]
    assert isinstance(post, GeneratedPost)


def test_generate_post_skips_critique_when_disabled():
    llm = _QueueLLM([_DRAFT_CAROUSEL_JSON])
    post = generate_post(_sample_brief(), WGS_BRAND_KIT, llm, enable_critique=False)
    assert llm.tiers_called == ["strong"]
    assert isinstance(post, GeneratedPost)


def _sample_draft() -> GeneratedPost:
    return GeneratedPost(
        slides=[
            CoverSlide(headline_word="PAUSE", script_word="first.", kicker="Before you react, breathe."),
            BodyTeachingSlide(
                heading="The inner critic",
                body="It shows up as certainty, but it's really just an old habit dressed up as truth.",
            ),
            BodyTeachingSlide(
                heading="The intuition",
                body="It's quieter, and it usually shows up as a question rather than a verdict.",
            ),
            BodyTeachingSlide(
                heading="The choice",
                body="Every time you notice the difference, choosing gets a little easier.",
            ),
            ClosingSlide(takeaway="You get to decide which one leads."),
            ConversationSlide(
                question="Which voice have you been listening to today?",
                cta=WGS_BRAND_KIT.signature_cta or "",
                handle=WGS_BRAND_KIT.handle,
            ),
        ],
        caption="The inner critic isn't always right.",
        hashtags=["#selfdoubt", "#growth"],
    )


def test_critique_asks_for_knowledge_hints_check_when_required_without_sources():
    """Logbook #14: taxonomy topics (career-pay-scale has knowledge_hints,
    ContentBrief.sources is always [] here) must get knowledge_hints-grounded
    critique language, not the source-traceability instruction — there are no
    sources to trace to outside the paste-link flow, and asking for that
    produced a contradictory prompt that rewrote accepted angles away."""
    llm = _QueueLLM(["no changes needed"])
    draft = GeneratedPost(
        slides=[StatSlide(kicker="Did you know", number="42%", supporting_line="a stat")],
        caption="a caption",
        hashtags=["#a"],
    )
    brief = _citation_required_brief()
    assert brief.sources == []
    assert brief.knowledge_hints
    critique_post(brief, WGS_BRAND_KIT, draft, llm)
    assert "traceable to the sources" not in llm.prompts[0]
    assert "well-established public knowledge" in llm.prompts[0]


def test_critique_asks_for_source_traceability_when_sources_present():
    """The paste-link flow (real pinned Source objects) keeps the original
    traceability instruction unchanged — only the sourceless taxonomy case
    changes behavior."""
    llm = _QueueLLM(["no changes needed"])
    draft = GeneratedPost(
        slides=[StatSlide(kicker="Did you know", number="42%", supporting_line="a stat")],
        caption="a caption",
        hashtags=["#a"],
    )
    brief = ContentBrief(
        topic_id="paste-link:abc123",
        topic_name="A Test Article",
        angle="an angle grounded in the article",
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
        hero_image_prompt="a prompt",
    )
    critique_post(brief, WGS_BRAND_KIT, draft, llm)
    assert "traceable to the sources" in llm.prompts[0]
    assert "well-established public knowledge" not in llm.prompts[0]


def test_critique_omits_citation_check_when_not_required():
    llm = _QueueLLM(["no changes needed"])
    critique_post(_sample_brief(), WGS_BRAND_KIT, _sample_draft(), llm)
    assert "traceable to the sources" not in llm.prompts[0]
    assert "well-established public knowledge" not in llm.prompts[0]


def test_critique_checks_kicker_clarity_only_when_cover_present():
    llm = _QueueLLM(["no changes needed"])
    critique_post(_sample_brief(), WGS_BRAND_KIT, _sample_draft(), llm)
    assert "kicker reads as a natural sentence" in llm.prompts[0]


def test_critique_checks_approach_structure_delivery():
    llm = _QueueLLM(["no changes needed"])
    critique_post(_sample_brief(), WGS_BRAND_KIT, _sample_draft(), llm)
    assert "'story' approach as defined above" in llm.prompts[0]


def test_regenerate_slide_returns_only_requested_slide():
    llm = _QueueLLM([json.dumps({"headline_word": "BREATHE", "script_word": "not react.", "kicker": "new kicker"})])
    slide = regenerate_slide(_sample_brief(), WGS_BRAND_KIT, _sample_draft(), 0, llm)
    assert slide.template_id == "carousel_cover"
    assert slide.headline_word == "BREATHE"
    assert llm.tiers_called == ["strong"]


def test_regenerate_slide_handles_body_teaching_role():
    llm = _QueueLLM([json.dumps({"heading": "New heading", "body": "A fresh two-sentence teaching moment here."})])
    slide = regenerate_slide(_sample_brief(), WGS_BRAND_KIT, _sample_draft(), 1, llm)
    assert slide.template_id == "carousel_body_teaching"
    assert slide.heading == "New heading"


def test_regenerate_slide_out_of_range_raises():
    llm = _QueueLLM([])
    with pytest.raises(IndexError):
        regenerate_slide(_sample_brief(), WGS_BRAND_KIT, _sample_draft(), 99, llm)


# Logbook #29: critique_post was checking the draft against _APPROACH_DEFINITIONS
# with nothing telling it slide count/shape is a fixed, non-negotiable brief
# constraint -- so an approach that "wants" more room than the format gives
# (single_image's 1 slide, most visibly) reliably produced a "needs more slides"
# complaint, which refine_post then complied with, overriding the brief's actual
# shape. These tests cover the fix: critique_post states the constraint explicitly
# (both formats, not just single_image), and refine_post restates it as a backstop.


def test_critique_states_fixed_slide_shape_for_carousel():
    llm = _QueueLLM(["no changes needed"])
    critique_post(_sample_brief(), WGS_BRAND_KIT, _sample_draft(), llm)
    prompt = llm.prompts[0]
    assert "slide count and roles are fixed by the brief" in prompt
    assert "NOT" in prompt and "something to critique" in prompt
    assert "exactly 6 slides" in prompt
    assert (
        "carousel_cover, carousel_body_teaching, carousel_body_teaching, carousel_body_teaching, "
        "carousel_closing, carousel_conversation" in prompt
    )
    assert "Never suggest the post needs more slides" in prompt
    # Deliberately narrow: content-quality critique must still be invited, not
    # suppressed wholesale by the new shape instruction.
    assert "A thin or underspecific single slide is still a fair critique" in prompt


def test_critique_states_fixed_slide_shape_for_single_image():
    llm = _QueueLLM(["no changes needed"])
    draft = GeneratedPost(
        slides=[StatSlide(kicker="Did you know", number="42%", supporting_line="a stat")],
        caption="a caption",
        hashtags=["#a"],
    )
    critique_post(_citation_required_brief(), WGS_BRAND_KIT, draft, llm)
    prompt = llm.prompts[0]
    assert "exactly 1 slide (single_stat)" in prompt
    assert "regardless of format" in prompt


def test_refine_prompt_restates_fixed_shape_as_backstop():
    llm = _QueueLLM(
        [
            json.dumps(
                {
                    "slides": [
                        {"kicker": "Did you know", "number": "42%", "supporting_line": "a stat"}
                    ],
                    "caption": "a caption",
                    "hashtags": ["#a"],
                }
            )
        ]
    )
    draft = GeneratedPost(
        slides=[StatSlide(kicker="Did you know", number="42%", supporting_line="a stat")],
        caption="a caption",
        hashtags=["#a"],
    )
    brief = _citation_required_brief()
    refine_post(brief, WGS_BRAND_KIT, draft, "this needs more room to explore", llm)
    prompt = llm.prompts[0]
    assert "slide count and roles are fixed at exactly 1 slide (single_stat)" in prompt
    assert "overrides anything the critique implies to the contrary" in prompt
    assert "keep the exact same number and type of slides as the draft" in prompt


def test_refine_still_respects_correct_slide_count_when_critique_agrees():
    """The backstop shouldn't break the normal, correct path: critique says no
    changes needed, refine returns the draft unchanged, same slide count."""
    llm = _QueueLLM([_DRAFT_CAROUSEL_JSON])
    post = refine_post(_sample_brief(), WGS_BRAND_KIT, _sample_draft(), "no changes needed", llm)
    assert len(post.slides) == 6


def test_body_slide_uses_old_fragment_schema_for_non_teaching_approach():
    llm = _QueueLLM(
        [
            json.dumps(
                {
                    "slides": [
                        {
                            "headline_word": "ASK",
                            "script_word": "yourself.",
                            "kicker": "What confident women do differently when doubt shows up.",
                        },
                        {
                            "statement_pre": "Doubt is loud,",
                            "statement_script": "but it isn't proof.",
                            "statement_post": "",
                        },
                        {
                            "statement_pre": "Certainty isn't",
                            "statement_script": "the same as truth.",
                            "statement_post": "",
                        },
                        {
                            "statement_pre": "You get to",
                            "statement_script": "choose",
                            "statement_post": "which voice leads.",
                        },
                        {"takeaway": "You get to choose which voice you listen to."},
                        {"question": "What would you tell a friend in your exact position?"},
                    ],
                    "caption": "a caption",
                    "hashtags": ["#a"],
                }
            )
        ]
    )
    post = draft_post(_non_teaching_brief(), WGS_BRAND_KIT, llm)
    assert len(post.slides) == 6
    assert post.slides[1].template_id == "carousel_body"


# --- Task "#19": carousel direct-write cover/body/closing schema rewrite ---


def _direct_write_raw_response(**overrides) -> str:
    fields = {
        "anchor": "a test anchor",
        "mood": "wisdom",
        "visual_subject": "a folded paper on a table",
        "caption": "a caption",
        "headline": "A Real Test Headline",
        "cover_body": "Real cover body copy for a test.",
        "body_1_text": "The first retold beat has a real accent word inside it.",
        "body_1_accent_phrase": "real accent word",
        "body_2_text": "The second retold beat also has a real accent word inside it.",
        "body_2_accent_phrase": "real accent word",
        "body_3_text": "The third retold beat has no matching substring for its own phrase.",
        "body_3_accent_phrase": "not present anywhere",
        "closing_takeaway": "A real closing. Across two real sentences.",
        "conversation_question": "What would you tell a friend right now?",
        "hashtags": ["#a"],
    }
    fields.update(overrides)
    return json.dumps(fields)


def test_parse_carousel_direct_response_cover_is_headline_and_cover_body_only():
    """Cover schema (task '#19'): headline -> CoverSlide.headline_word (the
    same 96px slot legacy's one-word headline used), cover_body -> a real new
    field, script_word/kicker hardcoded empty -- not asked of the model on
    this path at all."""
    post, anchor, mood, visual_subject = _parse_carousel_direct_response(
        _direct_write_raw_response(), WGS_BRAND_KIT
    )
    cover = post.slides[0]
    assert isinstance(cover, CoverSlide)
    assert cover.headline_word == "A Real Test Headline"
    assert cover.cover_body == "Real cover body copy for a test."
    assert cover.script_word == ""
    assert cover.kicker == ""
    assert anchor == "a test anchor"
    assert mood == "wisdom"
    assert visual_subject == "a folded paper on a table"


def test_parse_carousel_direct_response_body_drops_heading_keeps_accent_phrase():
    """Body schema (task '#19'): heading is dropped (hardcoded "" -- not asked
    of the model), accent_phrase carries through as its own field, verbatim,
    whether or not it actually turns out to be a real substring of body (that
    check is the prompt's job and the frontend's rendering fallback -- see
    CarouselBodyTeaching.tsx -- not this parsing step's)."""
    post, *_ = _parse_carousel_direct_response(_direct_write_raw_response(), WGS_BRAND_KIT)
    body_1, body_2, body_3 = post.slides[1], post.slides[2], post.slides[3]
    assert isinstance(body_1, BodyTeachingSlide)
    assert body_1.heading == ""
    assert body_1.body == "The first retold beat has a real accent word inside it."
    assert body_1.accent_phrase == "real accent word"
    assert body_1.accent_phrase in body_1.body
    assert body_3.accent_phrase == "not present anywhere"
    assert body_3.accent_phrase not in body_3.body  # a real possibility, not assumed away


def test_parse_carousel_direct_response_closing_is_the_raw_multi_sentence_field():
    """Closing schema (task '#19'): closing_takeaway flows straight through as
    ClosingSlide.takeaway, whatever length the model actually wrote -- no
    truncation or reshaping happens in parsing; the word-range check is
    validator.py's job (see test_validator.py's direct-write closing tests)."""
    post, *_ = _parse_carousel_direct_response(_direct_write_raw_response(), WGS_BRAND_KIT)
    closing = post.slides[4]
    assert isinstance(closing, ClosingSlide)
    assert closing.takeaway == "A real closing. Across two real sentences."
