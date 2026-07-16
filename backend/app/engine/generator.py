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
    BodyTeachingSlide,
    ClosingSlide,
    CoverSlide,
    GeneratedPost,
    QuoteSlide,
    Slide,
    SlideRole,
    StatSlide,
)
from app.providers.llm import LLMProvider, strip_json_fence
from app.taxonomy.approaches import TEACHING_BODY_APPROACHES
from app.taxonomy.voice_register import APPROACH_REGISTER

_ROLE_MODEL = {
    "carousel_cover": CoverSlide,
    "carousel_body": BodySlide,
    "carousel_body_teaching": BodyTeachingSlide,
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
    "carousel_body_teaching": (
        '{"heading": "a short lead-in label or phrase", '
        '"body": "1-2 full sentences of the actual teaching content — the real '
        'substance, not a fragment"}'
    ),
    "carousel_closing": '{"takeaway": "the one-line takeaway"}',
    "single_quote": '{"quote": "the quote text"}',
    "single_stat": (
        '{"kicker": "a short uppercase label", "number": "a big number or stat, e.g. 73%", '
        '"supporting_line": "one supporting sentence"}'
    ),
}

# One-line structural definition per approach — without this, a post can be labeled
# with an approach without its output actually delivering that approach's shape.
_APPROACH_DEFINITIONS: dict[str, str] = {
    "educational": (
        "teaches a specific mechanism or how-to — the actual steps or explanation must "
        "be present in the text, not just a promise that it's informative."
    ),
    "myth_vs_fact": (
        "states a clearly identifiable misconception AND a clearly identifiable "
        "correction, both explicit in the text — never merely implied."
    ),
    "checklist": (
        "delivers a concrete, enumerable set of distinct, actionable items — not one "
        "point restated in different words."
    ),
    "story": (
        "grounds the post in one concrete, relatable scenario or moment — a specific "
        "situation, not an abstract statement about situations in general."
    ),
    "stat_research": (
        "leads with a specific number or research finding stated as fact in the text, "
        "then interprets what it means for the reader."
    ),
    "question_reflection": (
        "poses a genuine, specific question the reader is meant to sit with — not a "
        "rhetorical throwaway — with the post's content oriented around exploring it."
    ),
    "framework": (
        "presents a named structure with distinct, labeled parts (steps, categories, "
        "phases) the reader could reapply on their own."
    ),
    "common_mistakes": (
        "explicitly names the mistake before correcting it — the mistake itself must "
        "be stated in the text, not just alluded to."
    ),
}

# The cover slide's kicker line must disambiguate the topic through a real sentence,
# never by degenerating into a taxonomy label — see _brief_system_prompt.
_KICKER_INSTRUCTION = (
    "The cover slide's kicker must make the concrete subject and real-world stakes "
    "unmistakable to a reader with zero other context, in one glance — through "
    'specific, concrete vocabulary woven into a real sentence a person would '
    'actually say (e.g. "what to say when they push back on your salary ask"), '
    "never by inserting the topic or category as a label or tag (e.g. never "
    '"Career — Salary Negotiation" or "This post is about salary negotiation"). '
    "If it reads like a label instead of a sentence, it has failed even if the "
    "subject is technically identifiable — the headline above it carries feeling, "
    "the kicker carries clarity, and neither should be sacrificed for the other."
)

# Peer-to-peer, active voice — applies across every approach and slide, not a
# structural requirement like _APPROACH_DEFINITIONS, so it stands on its own.
_VOICE_INSTRUCTION = (
    "Write the way a trusted friend actually talks to her, not at her — active "
    'voice, direct address ("you"), and the rhythm of real speech. Avoid polished '
    "copywriting cadences and avoid lecturing; this is a conversation between "
    "equals, not an authority handing down advice."
)

# Relatable, everyday specificity — a cross-cutting quality bar, distinct from the
# `story` approach's structural requirement to be built ENTIRELY around one
# scenario: this asks every approach to illustrate its point with something
# concrete, even a checklist or framework, not just `story` posts.
#
# Deliberately domain-neutral (logbook #30) — an earlier version of this
# instruction named literal example nouns ("a specific meeting, a specific text
# message, a specific conversation"), and the model was found to pattern-match to
# those literal examples rather than the underlying principle, inventing
# workplace/meeting scenes even on posts with no connection to work. The examples
# below name the QUALITY of specificity wanted, not a domain.
_SPECIFICITY_INSTRUCTION = (
    "Illustrate the point with a concrete, everyday moment she might actually be "
    "in right now — a real, identifiable scene (a specific sensation, a specific "
    "moment in her day, a specific interaction with someone in her life) rather "
    "than an abstract statement of a principle. Let the scene come from wherever "
    "the angle itself is actually grounded — her body, her home, a friendship, a "
    "quiet moment alone — not from a default assumption about where she spends "
    "her time. This applies whatever the approach's structure is — even a "
    "checklist or framework should be anchored in something recognizably real, "
    "not left as generic abstraction."
)

_ACTIONABILITY_INSTRUCTION = (
    "The post must leave her with something she can actually do, not just "
    "something to feel or understand — a specific next step, phrase, or shift in "
    "behavior, not only insight or validation."
)

# Judgment-based, not mandatory — unlike the instructions above, this is explicitly
# conditional, so its wording has to license skipping it rather than nudge toward
# always including it.
_SAVEABILITY_INSTRUCTION = (
    "If the topic and angle naturally lend themselves to a concrete, reusable "
    "takeaway — an exact phrase to say, a specific reframe, a short mental model "
    "— include it clearly enough that it's worth bookmarking. This is a judgment "
    "call, not a requirement: a purely relatable or feeling-oriented post should "
    "not be forced to manufacture a tip it doesn't organically have."
)

# The substance belongs on the slides, not the caption — without this, real
# content keeps landing in the caption as a paragraph restatement instead.
_CAPTION_INSTRUCTION = (
    "The caption's job is a hook that makes her want to swipe through the slides, "
    "plus optionally one closing thought that adds something new — never a "
    "restatement of the slide content in paragraph form. If a reader skips the "
    "caption entirely, the slides alone must already teach the thing; the caption "
    "is never where the only copy of the substance lives."
)


def slide_roles_for(brief: ContentBrief) -> list[SlideRole]:
    """Deterministic role sequence for this brief — the only place slide shape is
    decided. Carousel: cover, (n-2) body slides, closing — the body role is
    carousel_body_teaching (room for 1-2 full sentences) for approaches in
    TEACHING_BODY_APPROACHES, carousel_body (a single emphasis fragment) otherwise.
    Single image: the quote card for the poetic register, the stat card for the
    direct register (Section 6: same poetic/direct split that already resolves
    brand voice)."""
    if brief.format == Format.SINGLE_IMAGE:
        register = APPROACH_REGISTER[brief.approach.value]
        return ["single_quote"] if register == "poetic" else ["single_stat"]

    body_role: SlideRole = (
        "carousel_body_teaching" if brief.approach.value in TEACHING_BODY_APPROACHES else "carousel_body"
    )
    n = brief.slide_count
    body_count = max(n - 2, 0)
    return ["carousel_cover"] + [body_role] * body_count + ["carousel_closing"]


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
    if isinstance(slide, BodyTeachingSlide):
        return f"{slide.heading} {slide.body}"
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


def _citation_mode(brief: ContentBrief) -> str:
    """Which grounding a requires_citation brief actually has to work with: real
    pinned Source objects (paste-link flow only) get source-traceability language;
    everything else (every taxonomy topic — ContentBrief.sources is always [] there)
    falls back to knowledge_hints-based grounding. If a brief somehow has neither,
    there's nothing safe to instruct against, so no citation block is emitted at all
    — the topics.yaml startup loader (taxonomy/loader.py) is what should actually
    prevent this case from arising."""
    if not brief.requires_citation:
        return "none"
    if brief.sources:
        return "sources"
    if brief.knowledge_hints:
        return "knowledge_hints"
    return "none"


def _brief_system_prompt(brief: ContentBrief, brand_kit: BrandKit, roles: list[SlideRole]) -> str:
    voice_lines = "\n".join(f"- {s}" for s in brief.brand_voice_samples)
    forbidden = ", ".join(brand_kit.forbidden) or "none"

    citation_block = ""
    citation_mode = _citation_mode(brief)
    if citation_mode == "sources":
        source_lines = "\n".join(
            f"- {s.title} ({s.url or 'no url'}): {s.excerpt}" for s in brief.sources
        )
        citation_block = (
            "This post REQUIRES citation — every factual claim must be traceable to "
            f"these sources, never invented from memory:\n{source_lines}\n"
        )
    elif citation_mode == "knowledge_hints":
        hints = "; ".join(brief.knowledge_hints)
        citation_block = (
            "This post touches on factual claims. Stay within well-established, "
            f"widely-known public knowledge on this: {hints}. Do not invent a "
            "specific number, named study, quote, date, or precise statistic you "
            "are not confident is real — if unsure of an exact figure, describe "
            "the pattern qualitatively rather than citing a precise stat you "
            "can't verify.\n"
        )

    kicker_block = f"\n{_KICKER_INSTRUCTION}\n" if "carousel_cover" in roles else ""

    return (
        f"You write Instagram content for {brand_kit.brand_name}, a page for "
        f"{brand_kit.audience} Niche: {brand_kit.niche}\n\n"
        "The content itself — not just the tone — must draw on why this topic "
        "specifically lands differently for a woman: the particular pressure, "
        "socialization pattern, or double standard at play. Generic advice that "
        "would apply equally to anyone is not acceptable; the gendered dimension "
        "must be visible in the actual text.\n\n"
        f"{_VOICE_INSTRUCTION}\n\n"
        f"{_SPECIFICITY_INSTRUCTION}\n\n"
        f"{_ACTIONABILITY_INSTRUCTION}\n\n"
        f"{_SAVEABILITY_INSTRUCTION}\n\n"
        f"{_CAPTION_INSTRUCTION}\n\n"
        f"Brand voice traits: {', '.join(brand_kit.voice_traits)}\n"
        f"Voice examples in the register for this post:\n{voice_lines}\n\n"
        f"Never use: {forbidden}\n"
        f"Tone for this post: {', '.join(brief.tone)}\n"
        f"Approach: {brief.approach.value} — {_APPROACH_DEFINITIONS[brief.approach.value]}\n"
        f"Max words per slide (all text fields on that slide, combined): {brief.max_words_per_slide}\n"
        f"{citation_block}"
        f"{kicker_block}"
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
    citation_mode = _citation_mode(brief)
    if citation_mode == "sources":
        citation_instruction = (
            "This post requires citation — separately verify that every factual claim in "
            "the draft is directly traceable to the sources given above, and flag any claim "
            "that isn't (nothing invented from memory, no drifting beyond what the sources "
            "actually say). "
        )
    elif citation_mode == "knowledge_hints":
        citation_instruction = (
            "Separately verify the draft doesn't invent a specific number, named study, "
            "quote, date, or precise statistic beyond well-established public knowledge — "
            "flag anything that reads as a confident, specific figure that isn't safely "
            "verifiable. This is about fabricated specifics, not about the post's actual "
            "angle or premise — don't flag a claim just for being unsourced if it's "
            "well-established public knowledge. "
        )
    else:
        citation_instruction = ""
    kicker_instruction = (
        "Separately check whether the cover slide's kicker reads as a natural sentence "
        "with concrete, disambiguating detail — not a label or a restated topic/category "
        "name. "
        if "carousel_cover" in roles
        else ""
    )
    # logbook #29's actual root cause, not the one originally suspected: nothing told
    # critique that slide count/shape is a fixed, non-negotiable constraint from the
    # brief (slide_roles_for, decided in Python, blueprint decision 3) — so checking
    # the draft against _APPROACH_DEFINITIONS (below), which describes what an
    # approach ideally wants, reliably produced a "this needs more slides/structure"
    # complaint for any approach that wants more room than the format actually gives
    # (single_image's fixed 1 slide, most visibly). refine_post then complied,
    # expanding the slide count to satisfy a complaint that was never valid in the
    # first place. This instruction is deliberately narrow: it rules out shape
    # complaints, not content-quality complaints — a genuinely thin single slide is
    # still a fair critique.
    shape_instruction = (
        f"This post's slide count and roles are fixed by the brief and are NOT "
        f"something to critique, regardless of format: exactly {len(roles)} slide"
        f"{'s' if len(roles) != 1 else ''} ({', '.join(roles)}). Never suggest the "
        "post needs more slides, fewer slides, or a different structure to fully "
        "deliver the approach — even if the approach would normally want more room. "
        "If the approach's content genuinely doesn't fit, that's a content problem "
        "to solve within the existing slide(s) (tighten, prioritize, cut), not a "
        "shape problem to flag. A thin or underspecific single slide is still a "
        "fair critique — 'this needs another slide' is not. "
    )
    approach_instruction = (
        f"Separately check whether the post's structure actually delivers the "
        f"'{brief.approach.value}' approach as defined above, not merely labeled with "
        f"it — {_APPROACH_DEFINITIONS[brief.approach.value]} "
    )
    voice_instruction = (
        "Separately check whether it reads as active-voice, direct-address, "
        "peer-to-peer speech rather than polished copywriting or a lecture. "
    )
    specificity_instruction = (
        "Separately check whether the point is illustrated with a concrete, "
        "everyday moment or real scene rather than left as an abstract statement "
        "of a principle. "
    )
    actionability_instruction = (
        "Separately check whether it leaves her with something she can actually "
        "do — a specific next step, phrase, or behavior shift — not only insight "
        "or validation. "
    )
    saveability_instruction = (
        "Separately judge whether the topic and angle naturally had room for a "
        "concrete, reusable takeaway (an exact phrase, a specific reframe, a short "
        "mental model) and the draft missed it — only flag this if the opportunity "
        "was genuinely there; do not ask for one to be manufactured on a purely "
        "relatable or feeling-oriented post that doesn't call for it. "
    )
    prompt = (
        f"Here is a draft post:\n{draft.model_dump_json()}\n\n"
        "Critique it against the brand voice, the forbidden list, tone, word limits, and "
        f"whether it reads as specific rather than generic. {citation_instruction}"
        f"{shape_instruction}{kicker_instruction}{approach_instruction}{voice_instruction}"
        f"{specificity_instruction}{actionability_instruction}{saveability_instruction}"
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
    # Backstop for logbook #29: critique_post's own shape_instruction should already
    # stop a "needs more slides" complaint from ever being generated, but live
    # evidence showed the model overriding its own stated slide-count constraint
    # once already (mid-generation, unprompted) when a critique implied more
    # structure was needed — so the constraint isn't reliably strong enough stated
    # only once, in the system prompt. Restating it here, at the exact point the
    # model is told to "apply the critique," is the second layer.
    prompt = (
        f"Here is a draft post:\n{draft.model_dump_json()}\n\n"
        f"Critique:\n{critique}\n\n"
        "Apply the critique and return the improved final post in the same JSON shape. "
        "If the critique said no changes needed, return the draft unchanged.\n\n"
        f"The slide count and roles are fixed at exactly {len(roles)} slide"
        f"{'s' if len(roles) != 1 else ''} ({', '.join(roles)}) — this overrides "
        "anything the critique implies to the contrary. Even if the critique suggests "
        "the post needs more slides, fewer slides, or a different structure, keep "
        "the exact same number and type of slides as the draft and only change the "
        "content of those slides."
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
