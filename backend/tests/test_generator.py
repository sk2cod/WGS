import json

from app.engine.brief_builder import build_brief
from app.engine.generator import (
    critique_post,
    draft_post,
    generate_post,
    regenerate_slide,
    slide_roles_for,
)
from app.models.enums import Approach, Format
from app.models.post import BodySlide, ClosingSlide, CoverSlide, GeneratedPost, StatSlide
from app.taxonomy.loader import get_topics_by_id
from app.taxonomy.wgs_brand_kit import WGS_BRAND_KIT

# _sample_brief() -> carousel, roles = [carousel_cover, carousel_body, carousel_closing]
_DRAFT_CAROUSEL_JSON = json.dumps(
    {
        "slides": [
            {"headline_word": "PAUSE", "script_word": "first.", "kicker": "Before you react, breathe."},
            {
                "statement_pre": "Is this fear,",
                "statement_script": "or is this truth?",
                "statement_post": "",
            },
            {"takeaway": "You get to decide which one leads."},
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
        topic_id="mindset-reframing-self-doubt",
        topics_by_id=get_topics_by_id(),
        angle="the inner critic vs. the intuition that actually protects you",
        approach=Approach.STORY,
        mood="wisdom",
        format=Format.CAROUSEL,
        brand_kit=WGS_BRAND_KIT,
        memory=[],
    ).brief


def _citation_required_brief():
    return build_brief(
        topic_id="career-salary-negotiation",
        topics_by_id=get_topics_by_id(),
        angle="the numbers you need before you ask",
        approach=Approach.EDUCATIONAL,
        mood="bold",
        format=Format.SINGLE_IMAGE,
        brand_kit=WGS_BRAND_KIT,
        memory=[],
    ).brief


def test_slide_roles_for_carousel_is_cover_body_closing():
    assert slide_roles_for(_sample_brief()) == ["carousel_cover", "carousel_body", "carousel_closing"]


def test_slide_roles_for_single_image_direct_register_is_stat():
    assert slide_roles_for(_citation_required_brief()) == ["single_stat"]


def test_draft_post_parses_response():
    llm = _QueueLLM([_DRAFT_CAROUSEL_JSON])
    post = draft_post(_sample_brief(), WGS_BRAND_KIT, llm)
    assert len(post.slides) == 3
    assert post.slides[0].template_id == "carousel_cover"
    assert post.slides[1].template_id == "carousel_body"
    assert post.slides[2].template_id == "carousel_closing"
    assert post.caption == "The inner critic isn't always right."
    assert llm.tiers_called == ["strong"]


def test_draft_post_fills_closing_slide_from_brand_kit_not_llm():
    llm = _QueueLLM([_DRAFT_CAROUSEL_JSON])
    post = draft_post(_sample_brief(), WGS_BRAND_KIT, llm)
    closing = post.slides[2]
    assert closing.takeaway == "You get to decide which one leads."
    assert closing.signature == "with you,"
    assert closing.cta == WGS_BRAND_KIT.signature_cta
    assert closing.handle == WGS_BRAND_KIT.handle


def test_draft_post_strips_markdown_fence():
    llm = _QueueLLM([f"```json\n{_DRAFT_CAROUSEL_JSON}\n```"])
    post = draft_post(_sample_brief(), WGS_BRAND_KIT, llm)
    assert len(post.slides) == 3


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
            BodySlide(statement_pre="Is this fear,", statement_script="or is this truth?", statement_post=""),
            ClosingSlide(
                takeaway="You get to decide which one leads.",
                cta=WGS_BRAND_KIT.signature_cta or "",
                handle=WGS_BRAND_KIT.handle,
            ),
        ],
        caption="The inner critic isn't always right.",
        hashtags=["#selfdoubt", "#growth"],
    )


def test_critique_asks_for_citation_check_when_required():
    llm = _QueueLLM(["no changes needed"])
    draft = GeneratedPost(
        slides=[StatSlide(kicker="Did you know", number="42%", supporting_line="a stat")],
        caption="a caption",
        hashtags=["#a"],
    )
    critique_post(_citation_required_brief(), WGS_BRAND_KIT, draft, llm)
    assert "traceable to the sources" in llm.prompts[0]


def test_critique_omits_citation_check_when_not_required():
    llm = _QueueLLM(["no changes needed"])
    critique_post(_sample_brief(), WGS_BRAND_KIT, _sample_draft(), llm)
    assert "traceable to the sources" not in llm.prompts[0]


def test_regenerate_slide_returns_only_requested_slide():
    llm = _QueueLLM([json.dumps({"headline_word": "BREATHE", "script_word": "not react.", "kicker": "new kicker"})])
    slide = regenerate_slide(_sample_brief(), WGS_BRAND_KIT, _sample_draft(), 0, llm)
    assert slide.template_id == "carousel_cover"
    assert slide.headline_word == "BREATHE"
    assert llm.tiers_called == ["strong"]


def test_regenerate_slide_out_of_range_raises():
    import pytest

    llm = _QueueLLM([])
    with pytest.raises(IndexError):
        regenerate_slide(_sample_brief(), WGS_BRAND_KIT, _sample_draft(), 99, llm)
