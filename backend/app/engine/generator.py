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

from app.engine.angle_engine import DEFAULT_MOOD, VALID_MOODS, CarouselContext
from app.models.brand_kit import BrandKit
from app.models.brief import ContentBrief
from app.models.enums import Format
from app.models.topic import Topic
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

# Carousel direct-write only (draft_carousel_direct / draft_carousel_direct_from_source,
# task "#19" -- rewriting the direct-write cover/body/closing prompt and schema).
# carousel_cover and carousel_closing are shared render templates with the legacy
# chain, which still produces a one-word headline_word + a one-line kicker (cover)
# and a one-line takeaway (closing) -- _WORD_RANGE_FOR_ROLE's absence of a cover
# entry and its (10, 20) closing entry are still exactly right for legacy and are
# left untouched. These two ranges apply only when validate_post() is told
# carousel_writer="direct_write" (see validator.py's _range_for_role), for
# direct-write's real cover paragraph and real 2-4 sentence closing -- neither of
# which existed when the shared ranges above were sized. Initial estimates below,
# not yet load-bearing on a large real sample -- revisit if real trials show a
# consistent floor/ceiling miss, the same way _WORD_RANGE_FOR_ROLE itself was
# tuned against real renders.
_CAROUSEL_DIRECT_COVER_WORD_RANGE = (20, 45)
_CAROUSEL_DIRECT_CLOSING_WORD_RANGE = (24, 55)

_DIRECT_WRITE_WORD_RANGE_OVERRIDES: dict[str, tuple[int, int]] = {
    "carousel_cover": _CAROUSEL_DIRECT_COVER_WORD_RANGE,
    "carousel_closing": _CAROUSEL_DIRECT_CLOSING_WORD_RANGE,
}


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
        return f"{slide.headline_word} {slide.script_word} {slide.kicker} {slide.cover_body}"
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


def _citation_instruction_block(brief: ContentBrief) -> str:
    """Shared by _brief_system_prompt and the carousel direct-write port
    (_carousel_direct_system_prompt) so the two paths can never drift on
    wording — the knowledge_hints grounding text is exactly the fix logbook
    #14 shipped, reused verbatim rather than re-derived."""
    citation_mode = _citation_mode(brief)
    if citation_mode == "sources":
        source_lines = "\n".join(
            f"- {s.title} ({s.url or 'no url'}): {s.excerpt}" for s in brief.sources
        )
        return (
            "This post REQUIRES citation — every factual claim must be traceable to "
            f"these sources, never invented from memory:\n{source_lines}\n"
        )
    if citation_mode == "knowledge_hints":
        hints = "; ".join(brief.knowledge_hints)
        return (
            "This post touches on factual claims. Stay within well-established, "
            f"widely-known public knowledge on this: {hints}. Do not invent a "
            "specific number, named study, quote, date, or precise statistic you "
            "are not confident is real — if unsure of an exact figure, describe "
            "the pattern qualitatively rather than citing a precise stat you "
            "can't verify.\n"
        )
    return ""


def _brief_system_prompt(brief: ContentBrief, brand_kit: BrandKit, roles: list[SlideRole]) -> str:
    voice_lines = "\n".join(f"- {s}" for s in brief.brand_voice_samples)
    forbidden = ", ".join(brand_kit.forbidden) or "none"

    citation_block = _citation_instruction_block(brief)

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


# ============================================================================
# Carousel direct-write port (docs/logbook.md #43) -- OPEN, EXPERIMENTAL.
# Replaces the v1 checklist-patched writer (logbook #39: draft_post ->
# critique_post -> refine_post, sample_cell-dictated angle) for carousel ONLY,
# with the single-call design validated across this session's real testing
# (docs/direct-write-poc.md, the port test harness in logbook #40's
# investigation): one strong-tier call, free anchor pick guided by context
# rather than a dictated sub-concept/approach/entry-point cell, caption
# written first as the real piece. single_image is completely untouched --
# draft_post/critique_post/refine_post/generate_post above are still exactly
# what single_image uses, unmodified.
#
# Voice register is hardcoded to "poetic", not resolved via APPROACH_REGISTER
# -- there is no approach on this path to resolve it from (see below), and
# poetic is what carousel's already-restricted CAROUSEL_V1_APPROACHES pool
# (story/question_reflection, logbook #39) already implied for every carousel
# post before this. brief.approach is set by the caller to Approach.STORY as
# pure plumbing, not a real signal this path reads or reasons about --
# chosen specifically because it's the sole member CAROUSEL_V1_APPROACHES and
# TEACHING_BODY_APPROACHES have in common (confirmed by direct cross-check,
# docs/logbook.md), so slide_roles_for(brief) already resolves to
# carousel_body_teaching (routed here in logbook #44 for the extra room its
# 35-50 word range gives, up from carousel_body's 10-20) with zero changes to
# that function -- this also keeps validator.py's independent
# slide_roles_for(brief) call (_check_format) in agreement with what this
# writer's own parsing actually produces; picking an approach outside
# TEACHING_BODY_APPROACHES here would silently mismatch the two. Confirmed:
# this function never reads brief.approach or brief.entry_point for anything
# else, and never calls sample_cell/generate_angle.
# ============================================================================

# Deliberately NOT reusing _VOICE_INSTRUCTION (direct "you"-address,
# conversational-equals framing) or the _CAROUSEL_V1_* content-quality
# instructions above -- both were written for the checklist-patched writer
# this port replaces, and _VOICE_INSTRUCTION's direct-address framing
# actively contradicts rule 11 below (storyteller voice, avoid addressing an
# undefined reader), which is validated, not incidental. This prompt's voice
# foundation is ported from app/poc/prompt.py instead, adapted for
# production's actual slide shapes -- see the body-distillation instruction
# below for the biggest adaptation.

_CAROUSEL_DIRECT_BANNED_PHRASES = (
    "you are enough",
    "choose yourself",
    "protect your peace",
    "healing isn't linear",
    "you deserve",
    "give yourself permission",
    "trust the process",
    "everything happens for a reason",
)

# Rules 1-12, ported from app/poc/prompt.py (rules 1-12; rule 13, the
# selective-line-break rule, is dropped -- it existed for the POC's own
# single freeform-paragraph-per-slide template; production's body slides are
# a heading + a short paragraph across two separate fields, not one paragraph
# that could contain an internal line break, and the caption field isn't
# Satori-rendered at all). Adapted in three places: rule 2 now also excludes
# this topic's recent anchors; rule 7 and rule 9 each gained a clause
# connecting the caption-level instruction to the two explicit fields
# (closing_takeaway, the three body slides' heading + retold beat) this production shape
# asks for that the POC's own JSON never had.
_CAROUSEL_DIRECT_RULE_1 = """1. Open inside a specific, concrete scene — a person doing a small, particular
thing. Withhold the meaning of the detail for a beat. Never open with a
definition. (Naming the anchor immediately, in the first sentence, is also
valid when the anchor is striking enough on its own.) By the caption's second
beat at the latest, include at least one clause, phrase, or beat that gestures
toward the reader's own life — a single wondering, comparison, or echo is
enough; you do not need to explain the connection yet, only signal that one is
coming. Before finalizing, check: does the caption's first or second beat
contain that signal? If the caption stays entirely inside the anchor's own
history, mechanics, or terminology through its third beat with no such signal
anywhere yet, add one now rather than waiting for later."""

_CAROUSEL_DIRECT_TAXONOMY_ANCHOR_RULE = """2. Before settling on your anchor, think of 3 real candidates — genuine
historical practices, words, traditions, or scientific observations you are
highly confident actually exist and are documented, not paraphrases or
composites of things you've encountered. For each candidate, ask yourself
directly: could you point to where this is documented, or are you blending
several half-remembered things into something that sounds right? Discard any
candidate you can't answer that question confidently for, and discard any
candidate that appears in this topic's recently-used anchors below. Choose the
strongest of what remains. If none of your 3 candidates are ones you're
genuinely confident about, generate 3 more rather than proceeding with a
shaky one. The topic word itself should almost never be the anchor — the
anchor is something else entirely that the topic's meaning emerges through."""

# Paste-link's brief has a real pinned article (brief.sources), not a topic to
# freely recall an anchor from -- rule 2 here replaces free historical/cultural
# recall with "find the real anchor already inside the article excerpt," the
# core content-grounding adaptation logbook #51 makes for this brief shape.
# Rules 1 and 3-12 (shared below via _CAROUSEL_DIRECT_RULE_1 /
# _CAROUSEL_DIRECT_RULES_3_TO_12) are about voice and craft, not anchor
# origin, so they transfer unchanged -- only where the anchor comes from
# needs to differ.
_CAROUSEL_DIRECT_PASTE_LINK_ANCHOR_RULE = """2. Your anchor is not something you recall or invent — it is a specific
fact, scene, moment, or detail already stated in the pinned article excerpt
below. Read the excerpt first and find the one detail in it with the most
narrative weight: the most concrete, most specific, most human thing the
article actually says. Do not reach outside the excerpt for a supporting
historical parallel, statistic, or comparison, even a true one — if it is
not in the excerpt, it does not belong in this piece. If the excerpt is thin
on concrete detail, use its most specific stated fact as the anchor rather
than inventing texture to compensate."""

_CAROUSEL_DIRECT_RULES_3_TO_12 = """3. Stay with this one anchor for the entire piece. Never introduce a second,
unrelated anchor partway through — deepen the one you opened with instead.

4. If you cite a real person, study, or source, delay and soften the
attribution — let the idea land first, then introduce who found it, never
lead with a title. Prefer a role only ("a psychiatrist," "a marine
biologist," "a historian") over a real name. A named, real researcher turns
the moment into a citation rather than a discovery, even when delayed. Only
name someone when their specific identity is itself part of why the anchor
matters.

5. Tentative language — "perhaps," "I wonder," "maybe," "somewhere along the
way," "as though" — belongs at genuine reflective turns, the moments the
piece shifts from observation toward meaning. A story can have more than one
such turn. Never repeat it within the same beat, and never let it become the
default voice of a plain declarative sentence.

6. When you state what changes or what it means, make the subject of the
sentence a person or a physical thing doing something you could picture —
never an abstract noun (comfort, love, guilt, the feeling) performing an
action on its own. If you can't draw the sentence, rewrite it.

7. Close the caption by echoing something from the opening — a phrase, an
image, a detail — quietly returned to, not a new thought introduced. (The
closing_takeaway field has its own separate instruction, below — unlike the
caption's own ending, it is not asked to echo the opening.)

8. Never give an instruction or command to the reader. The reader arrives at
the meaning themselves.

9. The caption needs to actually travel: 4 to 7 real distinct beats. Every
beat must do a genuinely different job than the one before it (for example:
curiosity, then the anchor revealed, then why it mattered, then a turn toward
the reader, then the emotional truth, then an echo of the opening — not every
piece needs all of these, and not in this exact order, but each beat must
move the piece somewhere new). Never spend two consecutive beats making
substantially the same point in different words. Do not pad the caption with
more beats than the content genuinely earns. Before finalizing, check each
adjacent pair of beats: does the second one state a claim, or restate the one
before it using different words? If it's a restatement, cut it or replace it
with something that adds new ground. The three body-slide distillations (see
below) are pulled from this same beat structure, so getting the beats
genuinely distinct here is what makes the distillations distinct too.

10. Any biographical or factual detail you can't be fully certain of gets a
soft hedge ("said to," "known as," "believed to") rather than stated as flat
fact.

11. Write like a storyteller pulling the reader into one real scene, never
like an essay addressing an audience. Stay inside one specific person's
experience or one confident, unaddressed observation — never generalize the
reflective turn to a demographic or group ("I wonder how many women feel
this," "so many of us," "many people know this"). The universal feeling
should arrive because the specific detail was true, not because you named
who else might relate to it. Avoid hedged, invitational phrasing that
gestures at an undefined reader ("if you looked closely, you might
notice...," "you may have noticed...") — state what's true directly and
trust the detail to carry its own weight.

12. Punctuation should shape how a reader hears the sentence, not just close
it grammatically. Use a period where a thought genuinely stops. Use a comma
only for a light breath inside one continuous thought, never to splice two
complete sentences together. Use an em dash for a beat that turns,
interrupts, or lands a reveal. Break a sentence into two rather than
stacking three or more clauses behind commas."""

_CAROUSEL_DIRECT_RULES = (
    f"{_CAROUSEL_DIRECT_RULE_1}\n\n{_CAROUSEL_DIRECT_TAXONOMY_ANCHOR_RULE}\n\n"
    f"{_CAROUSEL_DIRECT_RULES_3_TO_12}"
)
# Paste-link variant (logbook #51) -- identical craft rules, anchor rule swapped.
_CAROUSEL_DIRECT_PASTE_LINK_RULES = (
    f"{_CAROUSEL_DIRECT_RULE_1}\n\n{_CAROUSEL_DIRECT_PASTE_LINK_ANCHOR_RULE}\n\n"
    f"{_CAROUSEL_DIRECT_RULES_3_TO_12}"
)

_CAROUSEL_DIRECT_EXAMPLES = """Four examples of the finished style — study the underlying principles, not
which specific opening move or how many turns each one uses; both an
immediate-naming opening and a withhold-and-reveal opening are valid:

Example A (names the anchor immediately, four separate reflective turns):
In many Japanese shrines, there's no wall to tell you you've arrived somewhere
sacred. Instead, there's a thick rope, twisted from rice straw. It's called a
shimenawa. It doesn't stop anyone from entering. It simply whispers: this
place is different.
No gate. No guard. No lock. Just a rope... and a quiet understanding that not
every space should be entered in the same way. Sometimes meaning is stronger
than force. I wonder if this is closer to what a boundary is supposed to feel
like.
Not walls built in fear. Not battles waiting to happen. Just a gentle way of
saying, "This part of me deserves care."
Somewhere along the way, I learned that protecting my peace required an
explanation. That "no" should sound kinder. That "not now" should
come wrapped in guilt. As though my boundaries needed permission before they
could exist.
But the rope never explains itself. It doesn't convince. It doesn't
apologise. It simply knows what it is protecting. Perhaps that's why it is
respected.
Maybe that's the invitation. To stop building walls so high that no one can
reach me... and begin placing ropes clear enough that people know how to meet
me. The strongest boundaries don't always push people away. Sometimes they
simply show people how to come closer — with care.

Example B (names the anchor after one beat of scene-setting):
Imagine if the earth was given permission to rest. Not after it failed. Not
after it was exhausted. Simply because rest was considered part of living
well. Thousands of years ago, it was.
In an ancient Hebrew tradition, every seventh year the land was left
untouched. No planting. No harvesting. No asking it for one more season. This
practice was called Shmita. A permission the earth received without
asking — the kind I still find hard to give myself.
The land wasn't resting because it had stopped being useful. It rested
because usefulness was never meant to come without renewal. Even the richest
soil was trusted to become still.
I wonder when I stopped extending myself the same kindness. Somewhere
along the way, rest became something I had to earn. Something reserved for
burnout. As though exhaustion were proof that I'd worked hard enough. The
earth was never asked to wait that long.
Maybe we've misunderstood what rest is. Not a reward. Not an interruption.
Not time lost. Perhaps it has always been part of the work itself. Just as
winter belongs to the tree, rest belongs to growth.
You are not a field in constant harvest. Some seasons ask you to bloom.
Others ask you to become quiet beneath the surface. Neither season is more
valuable than the other. Roots grow in both.

Example C (withholds the anchor one beat, one restrained turn):
Before she left for the date, her grandmother pressed a coin into her palm.
Not for anything, she said. Just in case.
It had a name — mad money. Kept separate from whatever a man might pay for
that night, hidden in a shoe or sewn into a hem. Enough for a cab home.
Enough to never need to ask.
It wasn't much, most of the time. A dime, later a dollar. It didn't need to
be much. It only needed to exist.
What no one tells you: it was never really about the money. It was about the
night never being able to trap you in it.
The coin usually came home unspent. It didn't need spending to have done its
job. It just needed to be there.

Example D (withholds the anchor one beat, one restrained turn):
She used to call most nights around eleven, no real reason, no agenda. I'd
pick up mid-thought and somehow already know what she needed before she got
to the point.
There's a word for that kind of understanding — the kind that arrives before
you've had to ask for it. In Japanese, it's called amae.
A psychiatrist spent years trying to explain it. He traced it all the way
back to infancy — to a mother reading her child's needs before the child even
has language for them.
What no one tells you: amae only survives if both people stay who they were.
Somewhere in the growing, the calls stopped landing the way they used to.
The understanding didn't leave because it wasn't real. It left because I'd
become someone it hadn't met yet."""


def _carousel_direct_context_block(topic: Topic, context: CarouselContext) -> str:
    lines = [f"Topic: {topic.name}", f"Category: {context.category}"]
    if context.seed_angles:
        lines.append(
            "Seed angles (context only, to help you understand what this topic "
            "means in this category — pick your own anchor freely, these are not "
            "requirements): " + "; ".join(context.seed_angles)
        )
    if context.recent_anchors:
        lines.append(
            "This topic's recently-used anchors — do not reuse any of these, per "
            "rule 2: " + "; ".join(context.recent_anchors)
        )
    return "\n".join(lines)


def _carousel_direct_body_distillation_instruction() -> str:
    # Routed to carousel_body_teaching (logbook #44), not carousel_body -- the
    # extra room (35-50 words vs. 10-20) is enough for a real retelling of a
    # beat, not just a compressed statement fragment, so this instruction now
    # matches the isolated POC's own already-validated slide-writing pattern
    # (docs/direct-write-poc.md Section 11: reworded, not copied, same
    # image/idea in a fresh sentence) rather than the "compress to one sharp
    # line" instruction carousel_body's much smaller range required.
    #
    # Logbook #52: stating the target as a number alone wasn't holding --
    # real output (#44's own testing, then live use) kept undershooting the
    # floor. Added an explicit count-and-check self-check step, same pattern
    # already hardened once for the POC's own rule 13 (docs/direct-write-poc.md
    # Section 9 -- a soft "sparingly" version didn't hold either, until it
    # became an explicit count-then-correct step). The correction is
    # deliberately "expand with more concrete detail," not "add words" --
    # padding/repetition to hit a number would trade one failure mode for
    # another already ruled out elsewhere in this prompt (rule 9's
    # restatement check).
    #
    # Task "#19": the heading field is dropped entirely (replaced by
    # accent_phrase, an in-line emphasis rather than a separate label line --
    # see CarouselBodyTeaching.tsx), and the beat-distinctness requirement is
    # restated here explicitly for the body slides specifically, not left to
    # only be implied by rule 9's caption-level version.
    lo, hi = _tolerant_word_range(*_WORD_RANGE_FOR_ROLE["carousel_body_teaching"])
    return (
        "After the caption is complete, select 3 of its real beats — in order, "
        "spanning the arc's actual development, not three variations on the "
        "opening — and retell each one fresh for its own slide: same moment, "
        "same image, same idea, in a different sentence. A reader may see both "
        "the slides and the caption on the same post, so a slide must never "
        "reuse the caption's own sentence almost word for word. Write each "
        "slide as flowing, editorial prose — full, complete sentences in the "
        "same register as the caption itself, never a clipped statement or a "
        "compressed fragment. Each of the 3 slides must be its own distinct "
        "beat doing a genuinely different job than the other two (the same "
        "distinctness rule 9 requires of the caption's own beats applies here "
        "too) — never a reworded repeat of another slide's point.\n"
        "Each slide also needs an accent_phrase: the single word or short "
        "phrase within that slide's own retold beat that matters most, copied "
        "verbatim from the body text you just wrote for that slide. It must be "
        "an exact, findable substring of that same slide's body — never a "
        "paraphrase, never borrowed from a different slide, and never more "
        f"than one accent_phrase per slide. Target {lo}-{hi} words for the "
        "retold beat itself. Before finalizing each body slide, count its "
        f"words. If the count is under {lo}, the beat is underdeveloped, not "
        "just concise — expand it with one more concrete sensory or narrative "
        "detail actually from that moment (what was seen, said, felt, or done) "
        "until it clears the floor, rather than padding with a restated idea "
        "or a generic elaboration."
    )


def _carousel_direct_cover_instruction() -> str:
    # Task "#19": replaces the old headline_word/script_word/kicker three-field
    # cover with exactly two fields, headline and cover_body -- _KICKER_INSTRUCTION
    # (the legacy chain's own cover instruction, unchanged) no longer applies here
    # at all, deliberately not folded in alongside this.
    #
    # Task "#20": the bridge-line sentence held only 2/4 in #19's real testing --
    # stating it as a soft "add one explicit sentence" instruction wasn't enough,
    # the same failure mode rule 1 and rule 9/the body-distillation floor already
    # went through before they were hardened into an explicit self-check. Applying
    # the identical proven pattern here: state the requirement, then a checkable
    # "before finalizing, check X; if not, add one now" step, rather than just
    # rewording the ask to sound stronger.
    lo, hi = _tolerant_word_range(*_CAROUSEL_DIRECT_COVER_WORD_RANGE)
    return (
        "Also write the cover — exactly two fields, headline and cover_body:\n"
        "headline: a short phrase (not one isolated word) drawn from the "
        "anchor or its central image — never the topic name itself, never a "
        "label.\n"
        "cover_body: 1-2 real sentences that make a reader want to keep "
        "swiping. If the anchor names a real person, place, tradition, or "
        "thing she might not already recognize, plainly spell out what "
        "category it belongs to (a country, a craft, a historical era, a "
        "field of study) — never assume she already knows what it is. Create "
        "curiosity by withholding what the anchor MEANS or why it matters, "
        "never by withholding basic facts about what it plainly is.\n"
        "When the anchor illustrates a separate, real-life theme rather than "
        "being the subject in its own right — true for almost every topic "
        "except a post that is directly about the anchor itself (e.g. a real "
        "historical figure's own story) — cover_body MUST include one "
        "explicit sentence bridging the anchor to the reader's own life. This "
        "is a requirement, not an optional nicety. Before finalizing "
        "cover_body, check: is the anchor itself the whole subject of this "
        "post, or does it illustrate something else? If it illustrates "
        "something else, does cover_body already contain a sentence "
        "connecting the anchor to the reader's own life? If it does not, add "
        "one now — do not leave cover_body as pure anchor-only curiosity when "
        "a bridge is required. Only skip the bridge line when the anchor "
        "genuinely is the whole subject of the post; forcing one in there "
        "would be a restatement, not a bridge.\n"
        f"Target {lo}-{hi} words combined across headline and cover_body."
    )


def _carousel_direct_closing_instruction() -> str:
    # Task "#19": replaces the old "closing_takeaway: one declarative line ...
    # see rule 7" constraint -- rule 7 no longer governs this field at all (see
    # the edit to _CAROUSEL_DIRECT_RULES_3_TO_12 above). closing_takeaway is a
    # real 2-4 sentence build now, not a one-line echo of the opening.
    #
    # Task "#22": real testing kept showing the caption's own actual ending
    # read stronger and more concrete than a closing_takeaway written as a
    # separate, from-scratch field -- the exact problem the body slides
    # already solve by deriving from the caption instead of inventing new
    # content (_carousel_direct_body_distillation_instruction above).
    # closing_takeaway now follows that identical pattern: it IS the
    # caption's own actual final beat, closely adapted for this slide, not a
    # new conclusion invented separately from what the caption already ends
    # on. "New feeling the piece hasn't already stated outright" is dropped
    # entirely -- it directly contradicted deriving from what the caption
    # has, in fact, already stated as its own ending.
    lo, hi = _tolerant_word_range(*_CAROUSEL_DIRECT_CLOSING_WORD_RANGE)
    return (
        f"closing_takeaway ({lo}-{hi} words, 2 to 4 full sentences — not one "
        "clipped line): this is not a new piece of writing. It is the "
        "caption's own actual ending — the same final beat, the same image, "
        "the same idea the caption itself closes on — closely adapted for "
        "this slide: retold in fresh sentence-level wording for its own "
        "screen, the same reworded-not-copied pattern the body slides above "
        "already use for their own beats. A reader may see both the caption "
        "and this slide on the same post, so it must never reuse the "
        "caption's own closing sentence almost word for word. It must also "
        "never reuse a body slide's own specific image or detail instead — "
        "if the caption's actual ending happens to overlap with a body "
        "slide's beat, adapt the ending's own wording, don't borrow the body "
        "slide's. Write it in plain, direct language; this is the moment for "
        "the piece's plainest sentences, not a place for wordplay or a "
        "clever turn for its own sake. Never phrase it as a question."
    )


def _carousel_direct_mood_instruction() -> str:
    return (
        'Also tag the piece\'s mood as exactly one of "wisdom", "bold", or '
        '"celebratory": wisdom for reflective/analytical pieces, bold for '
        "declarative/confident ones, celebratory for milestone/win pieces."
    )


# Adapted from generate_angle()'s existing visual_subject instruction
# (angle_engine.py) -- same proven guidance (concrete, photographable,
# never an abstract mood word or stock-photo trope), reworded to reference
# the anchor this path has instead of the topic+angle pair generate_angle()
# had. The actual wrapping of this into a styled DALL-E prompt reuses
# brief_builder._hero_image_prompt() unchanged -- see draft_carousel_direct's
# docstring; this function only asks the model to write the raw subject.
def _carousel_direct_visual_subject_instruction() -> str:
    return (
        "Also write visual_subject: 5-15 words naming ONE concrete image, "
        "object, or scene genuinely tied to THIS specific anchor — something "
        'a photographer could actually go photograph (e.g. "a straw rope '
        'tied across a threshold", "a folded bill inside a purse lining"). '
        'Never an abstract mood word like "transformation", "growth", or '
        '"balance", and never a generic stock-photo trope like a staircase '
        "or a winding path — it must be recognizably specific to this "
        "anchor, not swappable with any other post's."
    )


def _carousel_direct_system_prompt(brief: ContentBrief, brand_kit: BrandKit, topic: Topic, context: CarouselContext) -> str:
    voice_lines = "\n".join(f"- {s}" for s in brand_kit.voice_samples.poetic)
    forbidden = ", ".join(brand_kit.forbidden) or "none"
    banned_phrases = ", ".join(f'"{p}"' for p in _CAROUSEL_DIRECT_BANNED_PHRASES)
    citation_block = _citation_instruction_block(brief)

    conv_lo, conv_hi = _tolerant_word_range(*_WORD_RANGE_FOR_ROLE["carousel_conversation"])

    return (
        f"You are the writer for {brand_kit.brand_name} — for {brand_kit.audience} "
        f"Niche: {brand_kit.niche}\n\n"
        "The content itself — not just the tone — must draw on why this topic "
        "specifically lands differently for a woman: the particular pressure, "
        "socialization pattern, or double standard at play. Generic advice that "
        "would apply equally to anyone is not acceptable; the gendered dimension "
        "must be visible in the actual text.\n\n"
        f"Never sound: {forbidden}.\n\n"
        f"Never write any of these exact phrases or close paraphrases of them — "
        f"they are Instagram wallpaper text, the opposite of this brand's voice: "
        f"{banned_phrases}.\n\n"
        f"Reference voice — match this register, don't copy it:\n{voice_lines}\n\n"
        f"{_CAROUSEL_DIRECT_RULES}\n\n"
        f"{_CAROUSEL_DIRECT_EXAMPLES}\n\n"
        "The anchor field must contain only your final chosen anchor, a few words, "
        "no reasoning or alternatives — do your comparison silently, output only "
        "the result.\n\n"
        f"{_carousel_direct_mood_instruction()}\n\n"
        f"{_carousel_direct_visual_subject_instruction()}\n\n"
        "Write the caption before anything else. The caption is the real piece — "
        "write it exactly as you would if slides didn't exist, one continuous "
        "flowing telling, start to finish, with the beat structure rule 9 "
        "describes built into its own sentences.\n\n"
        f"{_carousel_direct_body_distillation_instruction()}\n\n"
        f"{_carousel_direct_cover_instruction()}\n\n"
        f"{_carousel_direct_closing_instruction()}\n\n"
        f"conversation_question: one genuine, open, unresolved question tied "
        f"directly to this anchor, {conv_lo}-{conv_hi} words, for the reader to "
        "sit with.\n\n"
        f"{citation_block}\n"
        "Also write 5-10 hashtags.\n\n"
        "Output as JSON:\n"
        "{\n"
        '  "anchor": "<the specific real thing this piece is built around, in a '
        'few words>",\n'
        '  "mood": "wisdom | bold | celebratory",\n'
        '  "visual_subject": "<5-15 words, one concrete photographable image tied '
        'to the anchor>",\n'
        '  "caption": "<the full piece, written first, start to finish, in '
        'flowing prose>",\n'
        '  "headline": "...", "cover_body": "...",\n'
        '  "body_1_text": "...", "body_1_accent_phrase": "...",\n'
        '  "body_2_text": "...", "body_2_accent_phrase": "...",\n'
        '  "body_3_text": "...", "body_3_accent_phrase": "...",\n'
        '  "closing_takeaway": "<2-4 sentences>",\n'
        '  "conversation_question": "...",\n'
        '  "hashtags": ["...", ...]\n'
        "}\n\n"
        f"{_carousel_direct_context_block(topic, context)}"
    )


def _parse_carousel_direct_response(raw: str, brand_kit: BrandKit) -> tuple[GeneratedPost, str, str, str]:
    data = json.loads(strip_json_fence(raw))

    anchor = str(data.get("anchor") or "").strip()
    mood = str(data.get("mood") or "").strip().lower()
    if mood not in VALID_MOODS:
        mood = DEFAULT_MOOD
    # Falls back to the anchor itself if the model omits this -- the anchor
    # is already "the specific real thing this piece is built around," a
    # reasonable stand-in image subject, same fallback shape
    # generate_angle()'s _parse_angle_response uses (fallback_visual_subject).
    visual_subject = str(data.get("visual_subject") or "").strip() or anchor

    # Task "#19": two cover fields (headline, cover_body) replace the old
    # three (headline_word, script_word, kicker) -- script_word/kicker are
    # hardcoded empty here, not dropped from CoverSlide itself, since that
    # Pydantic model (and CarouselCover.tsx) is shared with the legacy chain,
    # which still asks the model for all three. Same reasoning for
    # BodyTeachingSlide.heading below: dropped from THIS path's own prompt/
    # parsing, not from the shared model, since legacy still supplies it.
    raw_slides = [
        {
            "headline_word": data.get("headline", ""),
            "script_word": "",
            "kicker": "",
            "cover_body": data.get("cover_body", ""),
        },
        {
            "heading": "",
            "body": data.get("body_1_text", ""),
            "accent_phrase": data.get("body_1_accent_phrase", ""),
        },
        {
            "heading": "",
            "body": data.get("body_2_text", ""),
            "accent_phrase": data.get("body_2_accent_phrase", ""),
        },
        {
            "heading": "",
            "body": data.get("body_3_text", ""),
            "accent_phrase": data.get("body_3_accent_phrase", ""),
        },
        {"takeaway": data.get("closing_takeaway", "")},
        {"question": data.get("conversation_question", "")},
    ]
    # Routed to carousel_body_teaching, not carousel_body (logbook #44) -- see
    # this section's opening comment block for why brief.approach must be
    # Approach.STORY for this to stay consistent with validator.py's own
    # independent slide_roles_for(brief) call.
    roles: list[SlideRole] = [
        "carousel_cover",
        "carousel_body_teaching",
        "carousel_body_teaching",
        "carousel_body_teaching",
        "carousel_closing",
        "carousel_conversation",
    ]
    slides = [_build_slide(role, raw_slide, brand_kit) for role, raw_slide in zip(roles, raw_slides)]
    post = GeneratedPost(
        slides=slides,
        caption=str(data.get("caption", "")),
        hashtags=[str(h) for h in data.get("hashtags", [])],
    )
    return post, anchor, mood, visual_subject


def draft_carousel_direct(
    brief: ContentBrief,
    brand_kit: BrandKit,
    llm: LLMProvider,
    topic: Topic,
    context: CarouselContext,
) -> tuple[GeneratedPost, str, str, str]:
    """The carousel direct-write port's single call — no draft/critique/refine
    loop. `brief` is a caller-supplied, provisional ContentBrief: its
    `requires_citation`/`sources`/`knowledge_hints`/`format` are real and used
    (for _citation_instruction_block), but its `angle`/`mood` are not read
    here and should be treated as placeholders by the caller, since on this
    path both are only known once this call returns — unlike sample_cell/
    generate_angle, where they're decided before any writing starts. Callers
    should correct brief.angle/brief.mood from this function's returned
    (anchor, mood) before using the brief for validate_post or a MemoryRecord
    write.

    Returns (post, anchor, mood, visual_subject). visual_subject is the
    model's own raw image-subject text (same call, zero extra cost, same
    pattern as mood/the cover fields/conversation_question) -- it is NOT yet
    a styled hero_image_prompt. Callers should wrap it with the existing,
    reused (not rebuilt) `brief_builder._hero_image_prompt(visual_subject,
    mood)` -- the exact function generate_angle()'s own visual_subject
    output is already wrapped through via build_brief() -- to get
    brief.hero_image_prompt before calling the real image pipeline.

    No critique_post/refine_post call on this path, deliberately -- not an
    oversight. This mirrors what direct-write's isolated POC testing already
    found in `docs/direct-write-poc.md` Section 5 (direct-write outperformed
    eight rounds of patching the checklist-based prompt this replaces) and
    what the carousel-only real-content trials in this session's port test
    harness (docs/logbook.md #40's investigation) found: the single-call
    design held up cleanly against the specific failure modes the critique/
    refine backstops exist to catch (closing-declarative drift, reader-
    address leaking into a body slide) across every trial run. That evidence
    is real but from a small sample -- a handful of trials across a handful
    of topics, not the volume the checklist-based writer's backstops were
    hardened against over many logbook #39 rounds. If a future round of real
    output review finds the failure modes returning at scale, adding a
    narrow critique pass back for this path specifically (not the full
    three-call loop) is the documented next step, not a surprise."""
    system = _carousel_direct_system_prompt(brief, brand_kit, topic, context)
    prompt = "Write the piece now. Output only the JSON object described above, nothing else."
    raw = llm.complete(tier="strong", system=system, prompt=prompt, max_tokens=2000)
    return _parse_carousel_direct_response(raw, brand_kit)


def _carousel_direct_paste_link_system_prompt(brief: ContentBrief, brand_kit: BrandKit) -> str:
    """Paste-link variant of _carousel_direct_system_prompt (logbook #51).
    Same JSON shape and the same voice/craft rules, but built for a brief
    with a real pinned article (routes/sources.py::build_paste_link_brief),
    not a taxonomy Topic -- there is no Topic/CarouselContext for this brief
    at all (its topic_id is a synthetic per-article hash, never a real
    taxonomy entry), so this function never calls
    assemble_carousel_context() or takes a topic/context parameter, rather
    than passing dummy values through a signature built for something else.

    The anchor-selection rule is the one real content-level swap
    (_CAROUSEL_DIRECT_PASTE_LINK_RULES' rule 2, above): free historical/
    cultural recall doesn't fit a piece that has to stay inside what a real,
    specific article actually says, so rule 2 here points the model at the
    pinned excerpt instead. The citation grounding itself is NOT rebuilt --
    _citation_instruction_block's "sources" branch (confirmed correct for
    this exact brief shape in logbook #12) already embeds the full pinned
    excerpt(s) into the prompt verbatim, so it's reused as-is, same call as
    the taxonomy path uses for its own citation_block."""
    voice_lines = "\n".join(f"- {s}" for s in brand_kit.voice_samples.poetic)
    forbidden = ", ".join(brand_kit.forbidden) or "none"
    banned_phrases = ", ".join(f'"{p}"' for p in _CAROUSEL_DIRECT_BANNED_PHRASES)
    citation_block = _citation_instruction_block(brief)

    conv_lo, conv_hi = _tolerant_word_range(*_WORD_RANGE_FOR_ROLE["carousel_conversation"])

    return (
        f"You are the writer for {brand_kit.brand_name} — for {brand_kit.audience} "
        f"Niche: {brand_kit.niche}\n\n"
        "This piece reports on a real pinned article, not a freely-chosen topic — "
        "every factual claim must come from the article excerpt in the citation "
        "section below, never general knowledge, even when it feels safely true.\n\n"
        "The content itself — not just the tone — should draw on why this topic "
        "specifically lands differently for a woman, when the article's own "
        "content genuinely supports that: the particular pressure, socialization "
        "pattern, or double standard at play. Never invent a gendered angle the "
        "article doesn't itself give you material for — a straightforwardly "
        "reported piece is preferable to a stretched one.\n\n"
        f"Never sound: {forbidden}.\n\n"
        f"Never write any of these exact phrases or close paraphrases of them — "
        f"they are Instagram wallpaper text, the opposite of this brand's voice: "
        f"{banned_phrases}.\n\n"
        f"Reference voice — match this register, don't copy it:\n{voice_lines}\n\n"
        f"{_CAROUSEL_DIRECT_PASTE_LINK_RULES}\n\n"
        f"{_CAROUSEL_DIRECT_EXAMPLES}\n\n"
        "The anchor field must contain only the specific real detail from the "
        "article this piece is built around, a few words, no reasoning or "
        "alternatives — do your comparison silently, output only the result.\n\n"
        f"{_carousel_direct_mood_instruction()}\n\n"
        f"{_carousel_direct_visual_subject_instruction()}\n\n"
        "Write the caption before anything else. The caption is the real piece — "
        "write it exactly as you would if slides didn't exist, one continuous "
        "flowing telling, start to finish, with the beat structure rule 9 "
        "describes built into its own sentences.\n\n"
        f"{_carousel_direct_body_distillation_instruction()}\n\n"
        f"{_carousel_direct_cover_instruction()}\n\n"
        f"{_carousel_direct_closing_instruction()}\n\n"
        f"conversation_question: one genuine, open, unresolved question tied "
        f"directly to this anchor, {conv_lo}-{conv_hi} words, for the reader to "
        "sit with.\n\n"
        f"{citation_block}\n"
        "Also write 5-10 hashtags.\n\n"
        "Output as JSON:\n"
        "{\n"
        '  "anchor": "<the specific real detail from the article this piece is '
        'built around, in a few words>",\n'
        '  "mood": "wisdom | bold | celebratory",\n'
        '  "visual_subject": "<5-15 words, one concrete photographable image tied '
        'to the anchor>",\n'
        '  "caption": "<the full piece, written first, start to finish, in '
        'flowing prose>",\n'
        '  "headline": "...", "cover_body": "...",\n'
        '  "body_1_text": "...", "body_1_accent_phrase": "...",\n'
        '  "body_2_text": "...", "body_2_accent_phrase": "...",\n'
        '  "body_3_text": "...", "body_3_accent_phrase": "...",\n'
        '  "closing_takeaway": "<2-4 sentences>",\n'
        '  "conversation_question": "...",\n'
        '  "hashtags": ["...", ...]\n'
        "}\n"
    )


def draft_carousel_direct_from_source(
    brief: ContentBrief,
    brand_kit: BrandKit,
    llm: LLMProvider,
) -> tuple[GeneratedPost, str, str, str]:
    """Paste-link's own direct-write entry point (logbook #51) -- same
    single-call, no critique/refine design as draft_carousel_direct, for a
    brief built from a real pinned article
    (routes/sources.py::build_paste_link_brief) rather than a taxonomy
    Topic. Deliberately has no topic/context parameters and never calls
    assemble_carousel_context() -- there is no Topic behind a paste-link
    brief to look one up from (its topic_id is a synthetic per-article
    hash, e.g. "paste-link:a1b2c3..."), so the function signature reflects
    that rather than accepting dummy values for a Topic that doesn't exist.

    The anchor avoid-list/non-repetition mechanism
    (angle_engine.CarouselContext.recent_anchors) is deliberately not
    ported over here either -- investigated, not assumed to transfer.
    `recent_anchors` is built by matching MemoryRecord.topic_id against a
    Topic's real, recurring id (angle_engine.assemble_carousel_context);
    paste-link's topic_id is a one-off hash unique to each pasted article
    (hashlib.sha256 of the url-or-title), so the only way it would ever
    find a match is pasting the exact same URL or title twice -- the
    mechanism would be mechanically correct if wired in, but functionally
    almost always a no-op for this brief shape, unlike a real taxonomy
    topic that recurs across many posts over time. Not meaningfully
    applicable here, so it's left out rather than forced in for
    superficial parity with draft_carousel_direct.

    Returns (post, anchor, mood, visual_subject), the same shape
    draft_carousel_direct returns -- see that function's docstring for what
    each element means and how a caller should use them (correcting
    brief.angle/mood, wrapping visual_subject via
    brief_builder._hero_image_prompt())."""
    system = _carousel_direct_paste_link_system_prompt(brief, brand_kit)
    prompt = "Write the piece now. Output only the JSON object described above, nothing else."
    raw = llm.complete(tier="strong", system=system, prompt=prompt, max_tokens=2000)
    return _parse_carousel_direct_response(raw, brand_kit)
