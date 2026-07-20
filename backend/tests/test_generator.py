import json
from datetime import datetime, timezone

import pytest

from app.engine.brief_builder import build_brief
from app.engine.generator import (
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
#          carousel_closing, carousel_conversation] (conversation added logbook #39
# round 7 -- the first structural change in the v1 line of work)
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


def test_slide_roles_for_teaching_approach_uses_two_body_teaching_slides():
    assert slide_roles_for(_sample_brief()) == [
        "carousel_cover",
        "carousel_body_teaching",
        "carousel_body_teaching",
        "carousel_closing",
        "carousel_conversation",
    ]


def test_slide_roles_for_non_teaching_approach_uses_one_body_slide():
    assert slide_roles_for(_non_teaching_brief()) == [
        "carousel_cover",
        "carousel_body",
        "carousel_closing",
        "carousel_conversation",
    ]


def test_slide_roles_for_single_image_direct_register_is_stat():
    assert slide_roles_for(_citation_required_brief()) == ["single_stat"]


def test_draft_post_parses_response():
    llm = _QueueLLM([_DRAFT_CAROUSEL_JSON])
    post = draft_post(_sample_brief(), WGS_BRAND_KIT, llm)
    assert len(post.slides) == 5
    assert post.slides[0].template_id == "carousel_cover"
    assert post.slides[1].template_id == "carousel_body_teaching"
    assert post.slides[2].template_id == "carousel_body_teaching"
    assert post.slides[3].template_id == "carousel_closing"
    assert post.slides[4].template_id == "carousel_conversation"
    assert post.caption == "The inner critic isn't always right."
    assert llm.tiers_called == ["strong"]


def test_draft_post_fills_closing_slide_from_brand_kit_not_llm():
    llm = _QueueLLM([_DRAFT_CAROUSEL_JSON])
    post = draft_post(_sample_brief(), WGS_BRAND_KIT, llm)
    closing = post.slides[3]
    assert closing.takeaway == "You get to decide which one leads."
    assert closing.signature == "with you,"
    assert closing.cta == WGS_BRAND_KIT.signature_cta
    assert closing.handle == WGS_BRAND_KIT.handle


def test_draft_post_fills_conversation_slide_label_and_invite_from_defaults_not_llm():
    llm = _QueueLLM([_DRAFT_CAROUSEL_JSON])
    post = draft_post(_sample_brief(), WGS_BRAND_KIT, llm)
    conversation = post.slides[4]
    assert conversation.question == "Which voice have you been listening to today?"
    assert conversation.label == "- Conversation for today"
    assert conversation.invite == "I'd love to hear it."


def test_draft_post_strips_markdown_fence():
    llm = _QueueLLM([f"```json\n{_DRAFT_CAROUSEL_JSON}\n```"])
    post = draft_post(_sample_brief(), WGS_BRAND_KIT, llm)
    assert len(post.slides) == 5


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
            ClosingSlide(
                takeaway="You get to decide which one leads.",
                cta=WGS_BRAND_KIT.signature_cta or "",
                handle=WGS_BRAND_KIT.handle,
            ),
            ConversationSlide(question="Which voice have you been listening to today?"),
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
    assert "exactly 5 slides" in prompt
    assert (
        "carousel_cover, carousel_body_teaching, carousel_body_teaching, carousel_closing, "
        "carousel_conversation" in prompt
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
    assert len(post.slides) == 5


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
    assert len(post.slides) == 4
    assert post.slides[1].template_id == "carousel_body"
