"""Draft -> critique -> refine on the strong tier (blueprint Section 8). Not run on
images — the two lanes are independent so text quality is never traded against image
spend. Gated by ENABLE_CRITIQUE: when off, the draft is returned as-is.

Slide *shape* (which template each slide fills) is decided deterministically by
Python via `slide_roles_for` — never guessed by the model — because it's a fixed
function of format + approach (blueprint decision 3: "Python owns the brief and its
constraints; the LLM generates inside it"). The model only fills each role's content
fields; `carousel_closing`'s signature/cta/handle are brand-fixed copy, not
generated, so only its `takeaway` is asked for."""

from __future__ import annotations

import json

from app.models.brand_kit import BrandKit
from app.models.brief import ContentBrief
from app.models.enums import Format
from app.models.post import (
    BodySlide,
    ClosingSlide,
    CoverSlide,
    GeneratedPost,
    QuoteSlide,
    Slide,
    SlideRole,
    StatSlide,
)
from app.providers.llm import LLMProvider, strip_json_fence
from app.taxonomy.voice_register import APPROACH_REGISTER

_ROLE_MODEL = {
    "carousel_cover": CoverSlide,
    "carousel_body": BodySlide,
    "carousel_closing": ClosingSlide,
    "single_quote": QuoteSlide,
    "single_stat": StatSlide,
}

_ROLE_FIELDS_EXAMPLE = {
    "carousel_cover": (
        '{"headline_word": "ONE BOLD WORD", "script_word": "a short script phrase.", '
        '"kicker": "one supporting line"}'
    ),
    "carousel_body": (
        '{"statement_pre": "words before the emphasis (may be empty string)", '
        '"statement_script": "the one emphasized phrase", '
        '"statement_post": "words after the emphasis (may be empty string)"}'
    ),
    "carousel_closing": '{"takeaway": "the one-line takeaway"}',
    "single_quote": '{"quote": "the quote text"}',
    "single_stat": (
        '{"kicker": "a short uppercase label", "number": "a big number or stat, e.g. 73%", '
        '"supporting_line": "one supporting sentence"}'
    ),
}


def slide_roles_for(brief: ContentBrief) -> list[SlideRole]:
    """Deterministic role sequence for this brief — the only place slide shape is
    decided. Carousel: cover, (n-2) body slides, closing. Single image: the quote
    card for the poetic register, the stat card for the direct register (Section 6:
    same poetic/direct split that already resolves brand voice)."""
    if brief.format == Format.SINGLE_IMAGE:
        register = APPROACH_REGISTER[brief.approach.value]
        return ["single_quote"] if register == "poetic" else ["single_stat"]

    n = brief.slide_count
    body_count = max(n - 2, 0)
    return ["carousel_cover"] + ["carousel_body"] * body_count + ["carousel_closing"]


def _slides_shape_description(roles: list[SlideRole]) -> str:
    lines = [f"Slide {i} ({role}): {_ROLE_FIELDS_EXAMPLE[role]}" for i, role in enumerate(roles, start=1)]
    return "\n".join(lines)


def slide_text(slide: Slide) -> str:
    """All LLM-authored text on a slide, for word-limit/forbidden-phrase checks.
    carousel_closing's signature/cta/handle are brand-fixed, not generated, so
    they're excluded here."""
    if isinstance(slide, CoverSlide):
        return f"{slide.headline_word} {slide.script_word} {slide.kicker}"
    if isinstance(slide, BodySlide):
        return f"{slide.statement_pre} {slide.statement_script} {slide.statement_post}"
    if isinstance(slide, ClosingSlide):
        return slide.takeaway
    if isinstance(slide, QuoteSlide):
        return slide.quote
    if isinstance(slide, StatSlide):
        return f"{slide.kicker} {slide.number} {slide.supporting_line}"
    raise TypeError(f"unknown slide type: {type(slide)!r}")


def _build_slide(role: SlideRole, raw: dict, brand_kit: BrandKit) -> Slide:
    if role == "carousel_closing":
        return ClosingSlide(
            takeaway=str(raw.get("takeaway", "")),
            signature="with you,",
            cta=brand_kit.signature_cta or "",
            handle=brand_kit.handle,
        )
    return _ROLE_MODEL[role].model_validate(raw)


def _parse_post(raw: str, roles: list[SlideRole], brand_kit: BrandKit) -> GeneratedPost:
    data = json.loads(strip_json_fence(raw))
    raw_slides = data.get("slides")
    if not isinstance(raw_slides, list) or len(raw_slides) != len(roles):
        raise ValueError(f"expected {len(roles)} slide(s) ({roles}), got {raw_slides!r}")

    slides = [_build_slide(role, raw_slide, brand_kit) for role, raw_slide in zip(roles, raw_slides)]
    return GeneratedPost(
        slides=slides,
        caption=str(data.get("caption", "")),
        hashtags=[str(h) for h in data.get("hashtags", [])],
    )


def _brief_system_prompt(brief: ContentBrief, brand_kit: BrandKit, roles: list[SlideRole]) -> str:
    voice_lines = "\n".join(f"- {s}" for s in brief.brand_voice_samples)
    forbidden = ", ".join(brand_kit.forbidden) or "none"

    citation_block = ""
    if brief.requires_citation:
        source_lines = "\n".join(
            f"- {s.title} ({s.url or 'no url'}): {s.excerpt}" for s in brief.sources
        ) or "none"
        citation_block = (
            "This post REQUIRES citation — every factual claim must be traceable to "
            f"these sources, never invented from memory:\n{source_lines}\n"
        )

    return (
        f"You write Instagram content for {brand_kit.brand_name}, a page for "
        f"{brand_kit.audience} Niche: {brand_kit.niche}\n\n"
        f"Brand voice traits: {', '.join(brand_kit.voice_traits)}\n"
        f"Voice examples in the register for this post:\n{voice_lines}\n\n"
        f"Never use: {forbidden}\n"
        f"Tone for this post: {', '.join(brief.tone)}\n"
        f"Approach: {brief.approach.value}\n"
        f"Max words per slide (all text fields on that slide, combined): {brief.max_words_per_slide}\n"
        f"{citation_block}"
        "\nThis post has the following slides, each already assigned a fixed visual "
        "template — write ONLY the fields listed for its role, nothing else:\n"
        f"{_slides_shape_description(roles)}\n"
        "\nRespond with ONLY JSON, no markdown fence, in this exact shape: "
        '{"slides": [ <slide 1 fields>, <slide 2 fields>, ... ], "caption": "...", '
        '"hashtags": ["...", ...]}'
    )


def _draft_prompt(brief: ContentBrief) -> str:
    return (
        f"Topic: {brief.topic_name}\n"
        f"Angle: {brief.angle}\n"
        f"Goal: {brief.goal}\n"
        "Write the slides described above, plus a caption and 5-10 hashtags for this post."
    )


def draft_post(brief: ContentBrief, brand_kit: BrandKit, llm: LLMProvider) -> GeneratedPost:
    roles = slide_roles_for(brief)
    system = _brief_system_prompt(brief, brand_kit, roles)
    raw = llm.complete(tier="strong", system=system, prompt=_draft_prompt(brief), max_tokens=1500)
    return _parse_post(raw, roles, brand_kit)


def critique_post(
    brief: ContentBrief, brand_kit: BrandKit, draft: GeneratedPost, llm: LLMProvider
) -> str:
    roles = slide_roles_for(brief)
    system = _brief_system_prompt(brief, brand_kit, roles)
    citation_instruction = (
        "This post requires citation — separately verify that every factual claim in "
        "the draft is directly traceable to the sources given above, and flag any claim "
        "that isn't (nothing invented from memory, no drifting beyond what the sources "
        "actually say). "
        if brief.requires_citation
        else ""
    )
    prompt = (
        f"Here is a draft post:\n{draft.model_dump_json()}\n\n"
        "Critique it against the brand voice, the forbidden list, tone, word limits, and "
        f"whether it reads as specific rather than generic. {citation_instruction}"
        "Be concrete and short — list only real problems, or say 'no changes needed'."
    )
    return llm.complete(tier="strong", system=system, prompt=prompt, max_tokens=500)


def refine_post(
    brief: ContentBrief,
    brand_kit: BrandKit,
    draft: GeneratedPost,
    critique: str,
    llm: LLMProvider,
) -> GeneratedPost:
    roles = slide_roles_for(brief)
    system = _brief_system_prompt(brief, brand_kit, roles)
    prompt = (
        f"Here is a draft post:\n{draft.model_dump_json()}\n\n"
        f"Critique:\n{critique}\n\n"
        "Apply the critique and return the improved final post in the same JSON shape. "
        "If the critique said no changes needed, return the draft unchanged."
    )
    raw = llm.complete(tier="strong", system=system, prompt=prompt, max_tokens=1500)
    return _parse_post(raw, roles, brand_kit)


def generate_post(
    brief: ContentBrief,
    brand_kit: BrandKit,
    llm: LLMProvider,
    *,
    enable_critique: bool = True,
) -> GeneratedPost:
    draft = draft_post(brief, brand_kit, llm)
    if not enable_critique:
        return draft
    critique = critique_post(brief, brand_kit, draft, llm)
    return refine_post(brief, brand_kit, draft, critique, llm)


def regenerate_slide(
    brief: ContentBrief,
    brand_kit: BrandKit,
    post: GeneratedPost,
    slide_index: int,
    llm: LLMProvider,
) -> Slide:
    """Rewrite just one slide, in context of the rest of the post — cheaper than a
    full draft-critique-refine pass, for the editor's 'regenerate this slide'."""
    roles = slide_roles_for(brief)
    if not (0 <= slide_index < len(roles)):
        raise IndexError(f"slide_index {slide_index} out of range for {len(roles)} slide(s)")

    role = roles[slide_index]
    system = _brief_system_prompt(brief, brand_kit, roles)
    prompt = (
        f"Here is the current full post:\n{post.model_dump_json()}\n\n"
        f"Rewrite ONLY slide {slide_index + 1} (role {role}) with a fresh take on the same "
        f"angle — a different phrasing or emphasis, not a trivial tweak. Keep every other "
        "slide, the caption, and hashtags out of your response.\n"
        f"Respond with ONLY JSON, no markdown fence, in exactly this shape: "
        f"{_ROLE_FIELDS_EXAMPLE[role]}"
    )
    raw = llm.complete(tier="strong", system=system, prompt=prompt, max_tokens=400)
    raw_slide = json.loads(strip_json_fence(raw))
    return _build_slide(role, raw_slide, brand_kit)
