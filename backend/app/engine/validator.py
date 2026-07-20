"""Validation (Python, against the brief) — blueprint Section 8. Deterministic checks
only, no LLM: brand-voice/forbidden phrasings, citation presence when required, format
constraints (slide count, word limits), and repetition against content memory. Semantic
checks (does this *feel* preachy, does copy drift beyond a cited article) are the
critique pass's job upstream, not this validator's."""

from __future__ import annotations

from pydantic import BaseModel

from app.engine.generator import _citation_mode, _tolerant_word_cap, slide_text
from app.models.brand_kit import BrandKit
from app.models.brief import ContentBrief
from app.models.enums import Format
from app.models.memory import MemoryRecord
from app.models.post import GeneratedPost


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


def _check_format(brief: ContentBrief, post: GeneratedPost) -> list[str]:
    """logbook #39, round 8 correction: carousel's word cap now allows the same
    10% tolerance the model is actually told about (system prompt + critique,
    generator.py::_tolerant_word_cap) -- without this, a slide the model
    believed was compliant could still trip the app's "Needs a look" banner,
    the visible warning and the model's real instruction disagreeing.
    single_image keeps the original, untolerant cap unchanged."""
    errors = []
    if len(post.slides) != brief.slide_count:
        errors.append(f"expected {brief.slide_count} slide(s), got {len(post.slides)}")
    effective_cap = (
        _tolerant_word_cap(brief.max_words_per_slide)
        if brief.format == Format.CAROUSEL
        else brief.max_words_per_slide
    )
    for i, slide in enumerate(post.slides, start=1):
        word_count = len(slide_text(slide).split())
        if word_count > effective_cap:
            errors.append(
                f"slide {i} has {word_count} words, exceeds max_words_per_slide "
                f"({effective_cap})"
            )
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
