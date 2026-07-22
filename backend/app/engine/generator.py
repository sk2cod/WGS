"""Draft -> critique -> refine on the strong tier (blueprint Section 8). Not run on
images — the two lanes are independent so text quality is never traded against image
spend. Gated by ENABLE_CRITIQUE: when off, the draft is returned as-is.

Slide *shape* (which template each slide fills) is decided deterministically by
Python via `slide_roles_for` — never guessed by the model — because it's a fixed
function of format + approach (blueprint decision 3: "Python owns the brief and its
constraints; the LLM generates inside it"). The model only fills each role's content
fields; `carousel_closing`'s signature and `carousel_conversation`'s
label/invite/cta/handle are brand-fixed copy, not generated, so only `takeaway` and
`question` respectively are ever asked of the model."""

from __future__ import annotations

import json
import math

from app.models.brand_kit import BrandKit
from app.models.brief import ContentBrief
from app.models.enums import Format
from app.models.post import (
    BodySlide,
    BodyTeachingSlide,
    ClosingSlide,
    ConversationSlide,
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
    "carousel_conversation": ConversationSlide,
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
    # label, invite, cta, and handle are fixed brand copy (ConversationSlide
    # defaults) — only question is ever asked of the model, same pattern as
    # carousel_closing's signature.
    "carousel_conversation": '{"question": "the one genuine, open, unresolved question"}',
    "single_quote": '{"quote": "the quote text"}',
    "single_stat": (
        '{"kicker": "a short uppercase label", "number": "a big number or stat, e.g. 73%", '
        '"supporting_line": "one supporting sentence"}'
    ),
}

# Per-template (min, max) word ranges, replacing the single flat
# ContentBrief.max_words_per_slide=30 cap for the roles found to need one via
# real Satori renders against real POC-length content (docs/logbook.md). Each
# range is a floor as well as a ceiling now -- a slide that's too short for its
# template looks as broken as one that's too long, confirmed by real render:
# a 5-word carousel_body statement and a 26-word carousel_body_teaching slide
# both left large, unintentional-looking empty space.
#
# carousel_cover is deliberately absent -- its hero image absorbs any headline
# length, no problem was found, it keeps using brief.max_words_per_slide
# unchanged. single_quote is also absent: its problem was never word count
# (see SlideFrame/SingleQuote.tsx's vertical-centering fix), it also keeps the
# unchanged flat cap. single_stat is handled separately below, field by field,
# not as one combined range -- see _SINGLE_STAT_NUMBER_WORD_RANGE.
_WORD_RANGE_FOR_ROLE: dict[str, tuple[int, int]] = {
    "carousel_body": (10, 20),
    "carousel_body_teaching": (35, 50),
    "carousel_closing": (10, 20),
    "carousel_conversation": (15, 25),
}

# single_stat's `number` field is meant to hold a short numeral/stat ("73%", "4
# styles"), not a sentence -- it renders at 200px with no wrap guard. Previously
# unbounded by anything: a real production refine step put an ungrounded
# generalization ("Women face a tighter error margin", 5 words) in this field,
# which rendered as 5 lines of 200px text filling the entire canvas (confirmed
# live, docs/logbook.md). Checked as its own field, separate from
# supporting_line, because a combined slide-level word count can't catch a
# bloated `number` sitting next to a short `supporting_line` -- the two would
# average out and look fine on paper while `number` alone overflows.
_SINGLE_STAT_NUMBER_WORD_RANGE = (1, 3)
_SINGLE_STAT_SUPPORTING_LINE_WORD_RANGE = (15, 20)


def _tolerant_word_range(min_words: int, max_words: int) -> tuple[int, int]:
    """Same 10%-buffer philosophy as _tolerant_word_cap (logbook #39 round 8),
    applied to both ends of a range -- a slide one or two words under a
    template's floor isn't the same defect as one that's genuinely sparse,
    same as a few words over the ceiling isn't the same defect as genuinely
    bloated."""
    return math.floor(min_words * 0.9), math.ceil(max_words * 1.1)

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

# --- Carousel-only "v1" content-voice experiment (logbook #39) ---
# Replaces _SPECIFICITY_INSTRUCTION / _ACTIONABILITY_INSTRUCTION /
# _SAVEABILITY_INSTRUCTION / _CAPTION_INSTRUCTION above, but ONLY when
# brief.format == Format.CAROUSEL — single_image keeps every instruction above
# verbatim, unchanged. Experimental, pending real-output review before this either
# expands past carousel or gets promoted out of "v1" — see logbook #39.
_CAROUSEL_V1_ARC_INSTRUCTION = (
    "This post is one micro-essay, not a list of related points. Every slide stays "
    "with a single anchor — one concrete, real, specific thing drawn from history, "
    "culture, another language, nature, or literature: a tradition, a custom, an "
    "etymology, a philosophical idea, a moment from someone's real life. Favor an "
    "anchor that carries its own specific word or phrase from another era, culture, "
    "or discipline when one genuinely fits — this is what gives the post its "
    "editorial, researched feel, not generic inspiration. "
    # Appended in logbook #39's round-6 review, found through real organic use (not
    # controlled testing): a real generation abandoned the angle's own concrete
    # anchor for an unrelated, more evocative historical one partway through, with no
    # bridge between them — the "favor an anchor with its own word/phrase" sentence
    # above was incentivizing a swap toward whatever felt most evocative, rather than
    # staying with what the angle had already established.
    "This must still be the same anchor the angle itself already establishes — its "
    "specific concrete detail, moment, or thing. Do not replace it with a different "
    "anchor partway through the post, even a more evocative or historical one. If a "
    "historical, cultural, or linguistic reference genuinely adds something, it must "
    "be explicitly and clearly connected in the text to the angle's own anchor — the "
    "reader should never have to infer the link between two separate images on their "
    "own. One anchor, established once, carries the whole post. "
    "Never introduce a second, "
    "unrelated example partway through. Deepen the one you opened with instead of "
    "moving to a new one.\n\n"
    "Open on the anchor itself, named plainly, by slide 1 or 2 — concrete "
    "scene-setting is fine, abstract framing is not. Spend a slide or two with the "
    "anchor alone, on its own terms, before turning to the reader at all. Make one "
    "or two turns toward the reader or the human condition, no more, each carried "
    "by a tentative word — \"I wonder,\" \"perhaps,\" \"maybe,\" \"somewhere along "
    "the way.\" Do not let this language become the default register of every "
    "slide. "
    # Appended in logbook #39's round-6 review, found through real organic use: a
    # real generation had zero hedges anywhere, skipping the pivot moment entirely,
    # and nothing in the rule above (a ceiling, not a floor) would have flagged that.
    "At least one tentative moment (\"I wonder,\" \"perhaps,\" \"maybe,\" or similar) "
    "must appear somewhere in the post — in a body slide, the closing, or the "
    "caption. The pivot from anchor to reader cannot be skipped entirely. "
    "Once a turn has landed, the following line can state the reframe more "
    "plainly again. Close on an image or a general truth that lingers — never "
    "advice, never an instruction, never a command aimed at \"you.\" Let the "
    "reader draw the connection to their own life themselves.\n\n"
    "Biographical or factual specifics that aren't independently verifiable get a "
    "soft hedge (\"seemed to,\" \"known for\") rather than being stated as flat "
    "fact.\n\n"
    "Write in plain, declarative sentences everywhere except the one or two pivot "
    "points."
    "\n\n"
    # Appended after logbook #39's first real-output review round: critique reliably
    # (mis)flagged the cover's reader-facing kicker as a premature "turn to the
    # reader," and the model itself twice invented a second name for the same
    # anchor between the cover headline and the body.
    "The \"dwell with the anchor alone before turning to the reader\" rule applies "
    "to the body slides. The cover's kicker may still gesture toward the reader as "
    "its own hook — that is its separate, established job and is not a violation. "
    "If the anchor has a specific name or term, use that exact same word on the "
    "cover headline as when it's introduced in the body — don't invent a second "
    "name for the same anchor."
    "\n\n"
    # Appended in logbook #39's round-3 review: the "exact same word" rule above
    # was written with single coined terms in mind and doesn't cleanly fit a
    # quote-type anchor, where the body naturally continues the scene/narrative
    # rather than re-quoting the phrase itself.
    "This applies to a single coined term or named concept (e.g. amae, nemawashi). "
    "If the anchor is a quote or phrase rather than a single term (e.g. \"Noli me "
    "tangere\"), the body doesn't need to restate it verbatim as long as the "
    "narrative stays visibly anchored to the same quote/scene throughout."
    "\n\n"
    # Appended in logbook #39's round-5 review, found via direct prose review (not a
    # structural bug report): refine was inserting an unhedged, direct question into
    # the anchor-introduction body slide itself — the slide meant to dwell on the
    # anchor alone — to satisfy question_reflection's approach-fidelity check, which
    # names no location for that question. A different failure mode than the closing-
    # question override fixed in round 4: an early body slide, not the closing, and
    # not hedged as a tentative pivot at all.
    "The slide(s) spent dwelling on the anchor alone must contain no reader-address "
    "of any kind — no \"you,\" no question, nothing aimed at the reader — full stop. "
    "If the approach requires a genuine question somewhere in the post, it belongs "
    "in the caption or, at most, the one designated pivot slide later in the "
    "carousel, phrased with tentative language, never as a blunt question dropped "
    "into the anchor's introduction."
    "\n\n"
    # Added in logbook #39's round 7 — the first structural (not prompt-only)
    # change in this line of work: a real carousel_conversation slide, matching
    # the locked hand-written v1 reference, now exists after carousel_closing.
    # This guidance is for its one model-written field, question.
    "The final conversation-slide question must be a genuine, open, unresolved "
    "question tied directly to this post's specific anchor — not a generic "
    "engagement prompt. It should feel like a natural continuation of the "
    "anchor's own image, the way a reader would ask it back to themselves."
    "\n\n"
    # Added in logbook #39's round 8, alongside raising body slides 1-2 -> 3:
    # anti-padding + split guidance, adapted from a proven pattern found by
    # auditing a separate project's carousel mechanism, not invented fresh.
    "You have three body slides — use as many as the content genuinely needs, "
    "but do not pad to fill all three, and do not force one idea across "
    "multiple slides just to use the space available. If a single slide's "
    "content has more than one distinct fact or beat genuinely competing for "
    "room — especially when a reframe depends on a contrast between two "
    "things — split it across two slides rather than compressing both into "
    "one. Each body slide should do one clear job."
)

_CAROUSEL_V1_CAPTION_INSTRUCTION = (
    "The caption mirrors the whole post's arc in prose — the same anchor, the same "
    "movement from observation to reframe. It is a second, complete telling of the "
    "same micro-essay, not a summary, teaser, or restatement."
)

_CAROUSEL_V1_SPECIFICITY_ACTIONABILITY_SAVEABILITY_INSTRUCTION = (
    "This post does not need to give the reader something to do. A closing "
    "reflection or an open question is just as valid an ending as a concrete "
    "action step. Do not force advice or a takeaway if the anchor's reframe "
    "doesn't call for one."
)


def slide_roles_for(brief: ContentBrief) -> list[SlideRole]:
    """Deterministic role sequence for this brief — the only place slide shape is
    decided. Carousel: cover, 3 body slides, closing, conversation — 6 slides
    total, fixed regardless of approach (logbook #39, round 8 — previously body
    count varied 1-2 by TEACHING_BODY_APPROACHES; the confirmed final v1 shape
    always uses 3, on the understanding that the arc instruction's anti-padding
    guidance, not slide count, is what should stop thin content from being
    stretched to fill them). The body *role* itself (carousel_body_teaching vs
    carousel_body) still varies by approach — TEACHING_BODY_APPROACHES still
    gets the fuller per-slide field, just 3 of it now, not 2. Single image: the
    quote card for the poetic register, the stat card for the direct register
    (Section 6: same poetic/direct split that already resolves brand voice).

    carousel_conversation (logbook #39, round 7 — the first structural, not
    prompt-only, change in the v1 line of work) is appended unconditionally after
    carousel_closing for every carousel brief, regardless of approach — the real
    CTA/question slide matching the locked hand-written v1 reference. single_image
    is completely untouched by this."""
    if brief.format == Format.SINGLE_IMAGE:
        register = APPROACH_REGISTER[brief.approach.value]
        return ["single_quote"] if register == "poetic" else ["single_stat"]

    body_role: SlideRole = (
        "carousel_body_teaching" if brief.approach.value in TEACHING_BODY_APPROACHES else "carousel_body"
    )
    return ["carousel_cover"] + [body_role] * 3 + ["carousel_closing", "carousel_conversation"]


# Added in logbook #39's round 8: a real near-miss (37 vs. 30 words) showed a
# hard cap with no tolerance flags trivial overages as if they were the same
# defect as a genuinely bloated slide. 10% buffer, rounded up. Carousel-only
# (corrected in the same round after first being applied universally by
# mistake) — applied to the system prompt's stated cap, critique's own
# enforcement of it, and validator.py's deterministic _check_format, so what
# the model is told, what critique enforces, and what the app's own
# validation warning shows all agree. single_image keeps the original,
# untolerant cap everywhere.
def _tolerant_word_cap(cap: int) -> int:
    return math.ceil(cap * 1.1)


def _word_target_text_for_role(role: SlideRole, brief: ContentBrief) -> str:
    """Per-slide word guidance shown inline next to that slide's shape, replacing
    the old single blanket cap stated once for the whole post."""
    carousel = brief.format == Format.CAROUSEL
    role_range = _WORD_RANGE_FOR_ROLE.get(role)
    if role_range is not None:
        lo, hi = _tolerant_word_range(*role_range) if carousel else role_range
        return f"{lo}-{hi} words total across this slide's fields"
    if role == "single_stat":
        num_lo, num_hi = _SINGLE_STAT_NUMBER_WORD_RANGE
        sup_lo, sup_hi = _SINGLE_STAT_SUPPORTING_LINE_WORD_RANGE
        return (
            f"number: {num_lo}-{num_hi} words, a short numeral/stat only, never a "
            f"sentence (this field renders at 200px and overflows badly if long); "
            f"supporting_line: {sup_lo}-{sup_hi} words"
        )
    cap = _tolerant_word_cap(brief.max_words_per_slide) if carousel else brief.max_words_per_slide
    return f"up to {cap} words total across this slide's fields"


def _slides_shape_description(brief: ContentBrief, roles: list[SlideRole]) -> str:
    lines = [
        f"Slide {i} ({role}): {_ROLE_FIELDS_EXAMPLE[role]} — target "
        f"{_word_target_text_for_role(role, brief)}"
        for i, role in enumerate(roles, start=1)
    ]
    return "\n".join(lines)


def slide_text(slide: Slide) -> str:
    """All LLM-authored text on a slide, for word-limit/forbidden-phrase checks.
    carousel_closing's signature and carousel_conversation's label/invite/cta/handle
    are brand-fixed, not generated, so they're excluded here."""
    if isinstance(slide, CoverSlide):
        return f"{slide.headline_word} {slide.script_word} {slide.kicker}"
    if isinstance(slide, BodySlide):
        return f"{slide.statement_pre} {slide.statement_script} {slide.statement_post}"
    if isinstance(slide, BodyTeachingSlide):
        return f"{slide.heading} {slide.body}"
    if isinstance(slide, ClosingSlide):
        return slide.takeaway
    if isinstance(slide, ConversationSlide):
        return slide.question
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
        )
    if role == "carousel_conversation":
        # cta/handle moved here from carousel_closing in round 8 -- it's the
        # true last slide as of round 7, they were a leftover from before.
        return ConversationSlide(
            question=str(raw.get("question", "")),
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

    # Per-template word targets, not one flat number for the whole post (see
    # _WORD_RANGE_FOR_ROLE / _word_target_text_for_role) — real Satori renders
    # against real content found a single flat cap left some templates
    # (carousel_body_teaching) looking sparse and others (carousel_body,
    # carousel_closing) too thin at the low end, with no floor at all before
    # this. Stated inline per slide in _slides_shape_description below, not
    # here, since the right target genuinely differs by template.
    word_cap_line = (
        "Word targets are given per slide below, next to that slide's shape — "
        "treat them as a comfortable range, not a hard wall; a few words over "
        "or under a target alone is not a defect.\n"
    )

    # Carousel-only "v1" content-voice experiment (logbook #39) — single_image takes
    # the else branch, completely unchanged from before this experiment existed.
    if brief.format == Format.CAROUSEL:
        content_quality_block = (
            f"{_CAROUSEL_V1_ARC_INSTRUCTION}\n\n"
            f"{_CAROUSEL_V1_SPECIFICITY_ACTIONABILITY_SAVEABILITY_INSTRUCTION}\n\n"
            f"{_CAROUSEL_V1_CAPTION_INSTRUCTION}"
        )
    else:
        content_quality_block = (
            f"{_SPECIFICITY_INSTRUCTION}\n\n"
            f"{_ACTIONABILITY_INSTRUCTION}\n\n"
            f"{_SAVEABILITY_INSTRUCTION}\n\n"
            f"{_CAPTION_INSTRUCTION}"
        )

    return (
        f"You write Instagram content for {brand_kit.brand_name}, a page for "
        f"{brand_kit.audience} Niche: {brand_kit.niche}\n\n"
        "The content itself — not just the tone — must draw on why this topic "
        "specifically lands differently for a woman: the particular pressure, "
        "socialization pattern, or double standard at play. Generic advice that "
        "would apply equally to anyone is not acceptable; the gendered dimension "
        "must be visible in the actual text.\n\n"
        f"{_VOICE_INSTRUCTION}\n\n"
        f"{content_quality_block}\n\n"
        f"Brand voice traits: {', '.join(brand_kit.voice_traits)}\n"
        f"Voice examples in the register for this post:\n{voice_lines}\n\n"
        f"Never use: {forbidden}\n"
        f"Tone for this post: {', '.join(brief.tone)}\n"
        f"Approach: {brief.approach.value} — {_APPROACH_DEFINITIONS[brief.approach.value]}\n"
        f"{word_cap_line}"
        f"{citation_block}"
        f"{kicker_block}"
        "\nThis post has the following slides, each already assigned a fixed visual "
        "template — write ONLY the fields listed for its role, nothing else:\n"
        f"{_slides_shape_description(brief, roles)}\n"
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
    # Carousel-only "v1" content-voice experiment (logbook #39): replaces the three
    # checks below with a single connected-narrative checklist. single_image takes
    # the else branch, completely unchanged from before this experiment existed.
    if brief.format == Format.CAROUSEL:
        # Tightened in logbook #39's round-3 review: same substantive checks as
        # before, consolidated from 8 sentences into 4 so critique has less ground
        # to cover per call, on top of round 2's max_tokens increase (below).
        content_quality_instruction = (
            "Confirm one anchor holds the whole carousel — a second, unrelated "
            "example is only a problem if it appears after slide 1 — and that it's "
            "named plainly by slide 1 or 2, before any body slide turns to the "
            "reader. "
            "Confirm tentative language (\"I wonder,\" \"perhaps,\" and similar) "
            "appears at most once or twice, and no slide gives the reader a direct "
            "instruction or command. "
            "Confirm the caption is a full second telling of the arc, not a hook, "
            "teaser, or summary, and that the closing slide is declarative, not a "
            "literal question — even for question_reflection, which only needs a "
            "genuine open question somewhere in the arc, not on the closing line "
            "itself. "
            "A closing reflection or open question elsewhere, with no forced action "
            "step, is acceptable and should not be flagged as a missing takeaway. "
            # Appended in logbook #39's round-5 review: same ambiguity that caused
            # round 2's closing-question override (approach-fidelity naming no
            # location for the required question) was separately letting refine drop
            # an unhedged question into the anchor-introduction body slide instead —
            # found via direct prose review of round 1's mindset-rest/NIKSEN output.
            "Confirm no body slide other than the correctly-placed pivot slide "
            "addresses the reader directly — via \"you\" or a posed question — "
            "before the anchor's dwelling slides are complete. If "
            "question_reflection's required question isn't yet present anywhere in "
            "the post, the caption is the correct place for it, not an early body "
            "slide. "
            # Appended in logbook #39's round-6 review, found through real organic
            # use (not controlled testing): a real generation swapped the angle's own
            # anchor for an unrelated historical one partway through (mindset-
            # perfectionism), and a separate real generation had zero hedges anywhere
            # (mindset-boundaries), skipping the pivot moment entirely.
            "Confirm the post never introduces a materially different anchor from the "
            "one the angle itself established — flag it if a new historical, "
            "cultural, or object-based reference appears without being explicitly "
            "connected back to the angle's own concrete detail. "
            "Confirm at least one tentative moment (\"I wonder,\" \"perhaps,\" "
            "\"maybe,\" or similar) appears somewhere in the post — flag it if the "
            "pivot from anchor to reader is skipped entirely, not just if it's "
            "overused. "
            # Added in logbook #39's round 7, alongside the new carousel_conversation
            # slide (the first structural change in this line of work).
            "Confirm the conversation-slide question is genuinely tied to this "
            "post's anchor, not generic or interchangeable with any other post. "
            "This is where question_reflection's required open question belongs — "
            "the closing slide before it should stay declarative regardless. "
        )
    else:
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
        content_quality_instruction = (
            f"{specificity_instruction}{actionability_instruction}{saveability_instruction}"
        )
    # Added after logbook #39's first real-output review round, unconditionally for
    # both formats: cta/handle are hardcoded from brand_kit.signature_cta/handle in
    # _build_slide() and are never model output, so critique spending part of its
    # limited token budget flagging them (3 of 5 real carousel runs) was pure waste —
    # refine has no way to act on that feedback regardless of format. Moved from the
    # closing slide to the conversation slide in round 8 (cta/handle relocated there,
    # the true last slide as of round 7) — this instruction updated to match.
    cta_instruction = (
        "Do not evaluate or flag the conversation slide's cta or handle fields. "
        "They are fixed brand values from brand_kit.signature_cta/brand_kit.handle, "
        "not model-generated, and cannot be changed by refine. "
    )
    # Added in logbook #39's round 8, corrected to carousel-only in the same
    # round after being applied universally by mistake. Now per-template
    # (not one flat number) since each slide's own target is already stated
    # inline in the system prompt's shape description
    # (_word_target_text_for_role) — critique is told to check against those,
    # both a floor and a ceiling now, not just re-derive one shared cap here.
    # single_image reverts to no explicit tolerance statement, same as before.
    word_tolerance_instruction = (
        "Only flag a slide's word count if it falls outside that slide's own "
        "target range stated above for its template — both too far under and "
        "too far over count, with the 10% buffer on each end already applied "
        "there. A few words either side of a target alone is not a defect. "
        if brief.format == Format.CAROUSEL
        else ""
    )
    prompt = (
        f"Here is a draft post:\n{draft.model_dump_json()}\n\n"
        "Critique it against the brand voice, the forbidden list, tone, word limits, and "
        f"whether it reads as specific rather than generic. {citation_instruction}"
        f"{shape_instruction}{kicker_instruction}{approach_instruction}{voice_instruction}"
        f"{content_quality_instruction}{cta_instruction}{word_tolerance_instruction}"
        "Be concrete and short — list only real problems, or say 'no changes needed'."
    )
    # Carousel's checklist replaced 3 short checks with one longer one (#39), grew
    # further in round 2 (closing-declarative check), then got tightened back down in
    # round 3 (above) — but 800 tokens still truncated 3 of 5 real carousel critiques
    # in round 2, so this round also raises the ceiling to 1200 on top of the
    # tightened text, rather than relying on either change alone. single_image's
    # critique prompt only gained the short, exclusionary cta_instruction, which asks
    # the model to skip a check rather than perform an additional one, so its output
    # length isn't expected to grow — left at 500, unchanged.
    critique_max_tokens = 1200 if brief.format == Format.CAROUSEL else 500
    return llm.complete(tier="strong", system=system, prompt=prompt, max_tokens=critique_max_tokens)


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
    # Second backstop, same #29/#37 precedent as above, added in logbook #39's round
    # 4: round 3's diagnosis traced the closing-question override to the shared
    # system prompt's "an open question is just as valid an ending" line (read by
    # refine_post directly) plus a round-2 fix that only ever told critique to check
    # for a declarative closing, never refine_post to keep one — so, exactly like the
    # slide-count rule above, the constraint gets restated here a second time, at the
    # exact point the model applies the critique, independent of whether critique's
    # own note happened to mention the closing at all. Carousel-only: single_image
    # has no carousel_closing role for this to apply to.
    closing_declarative_instruction = (
        "\n\nKeep the closing slide declarative — an image or general truth, not a "
        "literal question — even if the approach is question_reflection, and "
        "regardless of what critique's note does or doesn't say about the closing "
        "specifically."
        if brief.format == Format.CAROUSEL
        else ""
    )
    # Third backstop, same #29/#37 precedent, added in logbook #39's round 5: the
    # question_reflection approach-fidelity check names no location for its required
    # question, and round-1 evidence (mindset-rest/NIKSEN, found by direct prose
    # review) showed refine dropping it into the anchor-introduction body slide
    # instead of the closing — a different location than round 4's fix covers, same
    # underlying ambiguity. Carousel-only, same reasoning as the backstop above.
    body_slide_question_instruction = (
        "\n\nIf you need to add a genuine question to satisfy the question_reflection "
        "approach, add it to the caption — not to a body slide that's meant to be "
        "dwelling on the anchor alone."
        if brief.format == Format.CAROUSEL
        else ""
    )
    # Fourth backstop, same #29/#37 two-layer pattern, added in logbook #39's round 6:
    # both found through real organic use of the live app, not controlled testing —
    # an anchor swap (mindset-perfectionism) and a missing hedge (mindset-boundaries).
    # Carousel-only, same reasoning as the two backstops above.
    anchor_lock_and_hedge_floor_instruction = (
        "\n\nIf critique flags an anchor swap, fix it by either returning to the "
        "angle's own original anchor or explicitly connecting the new reference back "
        "to it in the text — don't leave two disconnected images in the same post. "
        "If critique flags a missing hedge, add exactly one tentative moment at the "
        "natural pivot point — don't add more than one just because one was missing."
        if brief.format == Format.CAROUSEL
        else ""
    )
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
        f"{closing_declarative_instruction}"
        f"{body_slide_question_instruction}"
        f"{anchor_lock_and_hedge_floor_instruction}"
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
