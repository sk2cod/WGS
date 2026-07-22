"""Validation (Python, against the brief) — blueprint Section 8. Deterministic checks
only, no LLM: brand-voice/forbidden phrasings, citation presence when required, format
constraints (slide count, word limits), and repetition against content memory. Semantic
checks (does this *feel* preachy, does copy drift beyond a cited article) are the
critique pass's job upstream, not this validator's."""

from __future__ import annotations

from pydantic import BaseModel

from app.engine.generator import (
    _SINGLE_STAT_NUMBER_WORD_RANGE,
    _SINGLE_STAT_SUPPORTING_LINE_WORD_RANGE,
    _WORD_RANGE_FOR_ROLE,
    _citation_mode,
    _tolerant_word_cap,
    _tolerant_word_range,
    slide_roles_for,
    slide_text,
)
from app.models.brand_kit import BrandKit
from app.models.brief import ContentBrief
from app.models.enums import Format
from app.models.memory import MemoryRecord
from app.models.post import GeneratedPost, StatSlide


class ValidationResult(BaseModel):
    passed: bool
    errors: list[str] = []


def _check_forbidden(brand_kit: BrandKit, post: GeneratedPost) -> list[str]:
    text = " ".join([slide_text(s) for s in post.slides] + [post.caption]).lower()
    errors = []
    for term in brand_kit.forbidden:
        # entries like "engagement-bait CTAs (e.g. 'comment ❤️ if...')" carry a
        # parenthetical example — match on the literal phrase before it.
        needle = term.split(" (")[0].strip().lower()
        if needle and needle in text:
            errors.append(f"forbidden phrase present: {term!r}")
    return errors


def _check_slide_word_range(brief: ContentBrief, role: str, index: int, slide) -> list[str]:
    """Per-template (min, max) ranges replacing the old flat max_words_per_slide
    cap for the roles found to need one via real Satori renders (docs/logbook.md)
    -- carousel_body, carousel_body_teaching, carousel_closing, and
    carousel_conversation each get their own range, with the same 10% tolerance
    (both ends) as _tolerant_word_cap already used carousel-only. Roles absent
    from _WORD_RANGE_FOR_ROLE (carousel_cover, single_quote) keep the original
    flat brief.max_words_per_slide cap, unchanged -- no problem was found for
    either. single_stat is checked separately below, field by field, not folded
    into this combined-text check."""
    range_ = _WORD_RANGE_FOR_ROLE.get(role)
    if range_ is not None:
        min_words, max_words = _tolerant_word_range(*range_) if brief.format == Format.CAROUSEL else range_
        word_count = len(slide_text(slide).split())
        if word_count < min_words:
            return [
                f"slide {index} ({role}) has {word_count} words, below the "
                f"{min_words}-word floor for this template"
            ]
        if word_count > max_words:
            return [
                f"slide {index} ({role}) has {word_count} words, exceeds the "
                f"{max_words}-word ceiling for this template"
            ]
        return []

    if isinstance(slide, StatSlide):
        return _check_single_stat_fields(index, slide)

    effective_cap = (
        _tolerant_word_cap(brief.max_words_per_slide)
        if brief.format == Format.CAROUSEL
        else brief.max_words_per_slide
    )
    word_count = len(slide_text(slide).split())
    if word_count > effective_cap:
        return [
            f"slide {index} has {word_count} words, exceeds max_words_per_slide "
            f"({effective_cap})"
        ]
    return []


def _check_single_stat_fields(index: int, slide: StatSlide) -> list[str]:
    """number and supporting_line get independent ranges, not one combined
    slide-level word count -- a combined count can't catch a bloated `number`
    sitting next to a short `supporting_line`, which is exactly the shape of
    the real production bug this check exists for (docs/logbook.md): a 5-word
    generalization in `number` rendered as 5 lines of 200px text filling the
    whole canvas, while the slide's total word count looked unremarkable."""
    errors = []
    num_lo, num_hi = _SINGLE_STAT_NUMBER_WORD_RANGE
    number_words = len(slide.number.split())
    if not (num_lo <= number_words <= num_hi):
        errors.append(
            f"slide {index} (single_stat) number field has {number_words} word(s) "
            f"({slide.number!r}), expected {num_lo}-{num_hi} -- this field renders "
            "at 200px with no wrap guard and overflows badly outside a short "
            "numeral/stat"
        )
    sup_lo, sup_hi = _SINGLE_STAT_SUPPORTING_LINE_WORD_RANGE
    sup_words = len(slide.supporting_line.split())
    if not (sup_lo <= sup_words <= sup_hi):
        errors.append(
            f"slide {index} (single_stat) supporting_line has {sup_words} words, "
            f"expected {sup_lo}-{sup_hi}"
        )
    return errors


def _check_format(brief: ContentBrief, post: GeneratedPost) -> list[str]:
    """logbook #39, round 8: carousel's word cap allows the same 10% tolerance
    the model is actually told about (system prompt + critique) -- without
    this, a slide the model believed was compliant could still trip the app's
    "Needs a look" banner, the visible warning and the model's real
    instruction disagreeing. Per-template ranges (added on top of that same
    tolerance philosophy) replace the single flat cap for the roles real
    Satori renders found needed one -- see _check_slide_word_range."""
    errors = []
    if len(post.slides) != brief.slide_count:
        errors.append(f"expected {brief.slide_count} slide(s), got {len(post.slides)}")

    roles = slide_roles_for(brief)
    for i, (role, slide) in enumerate(zip(roles, post.slides), start=1):
        errors.extend(_check_slide_word_range(brief, role, i, slide))
    return errors


def _check_citation(brief: ContentBrief) -> list[str]:
    """Grounding for a citation-required brief comes from one of two places —
    real pinned Source objects (paste-link flow) or Topic.knowledge_hints (every
    other flow — logbook #14) — matching generator.py's _citation_mode(). Only
    flag a problem when neither is present: that's the paste-link flow
    producing a brief with no sources, the real bug this check exists to catch.
    A knowledge_hints-mode brief with empty sources is correct by design, not
    an error — sources are never populated outside paste-link. Empty
    knowledge_hints on a citation-required, sourceless brief also lands here;
    the startup loader guard (taxonomy/loader.py) should make that unreachable
    for real topics, so seeing it means that guard was bypassed."""
    if brief.requires_citation and _citation_mode(brief) == "none":
        return ["requires_citation is True but the brief has neither sources nor knowledge_hints"]
    return []


def _check_repetition(memory: list[MemoryRecord], fingerprint: str) -> list[str]:
    if any(r.fingerprint == fingerprint for r in memory):
        return [f"fingerprint {fingerprint!r} already exists in content memory"]
    return []


def validate_post(
    brief: ContentBrief,
    brand_kit: BrandKit,
    post: GeneratedPost,
    memory: list[MemoryRecord],
    fingerprint: str,
) -> ValidationResult:
    errors = [
        *_check_forbidden(brand_kit, post),
        *_check_format(brief, post),
        *_check_citation(brief),
        *_check_repetition(memory, fingerprint),
    ]
    return ValidationResult(passed=not errors, errors=errors)
