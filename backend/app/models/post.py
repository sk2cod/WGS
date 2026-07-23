"""Per-template slide content — mirrors frontend/lib/types.ts exactly (the render
contract, Section 8 of implementation-guide.md), so a slide the backend generates
needs no lossy reshaping before /api/render can draw it. `template_id` is a real
discriminator: the frontend uses the same field to pick which component and which
render call to make."""

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

SlideRole = Literal[
    "carousel_cover",
    "carousel_body",
    "carousel_body_teaching",
    "carousel_closing",
    "carousel_conversation",
    "single_quote",
    "single_stat",
]


class CoverSlide(BaseModel):
    # headline_word/script_word/kicker are the legacy chain's own three-field
    # cover shape, unchanged. cover_body is the carousel direct-write port's
    # field (task "#19"), added on top rather than replacing anything here,
    # since this model is shared with legacy (generator.py::_build_slide) --
    # direct-write hardcodes script_word/kicker to "" and headline_word holds
    # its own (possibly multi-word) headline; legacy leaves cover_body "".
    template_id: Literal["carousel_cover"] = "carousel_cover"
    headline_word: str    # one bold structural word (legacy) or a short headline phrase (direct-write) -- same 96px slot
    script_word: str      # legacy: one short script-accent phrase, e.g. "first.". Direct-write: always ""
    kicker: str            # legacy: one supporting line. Direct-write: always "" -- cover_body is this path's supporting copy
    cover_body: str = ""   # direct-write only: 1-2 real sentences of curiosity-building cover copy. Always "" for legacy


class BodySlide(BaseModel):
    template_id: Literal["carousel_body"] = "carousel_body"
    statement_pre: str     # words before the emphasized phrase (may be empty)
    statement_script: str  # exactly one emphasized phrase, script font
    statement_post: str    # words after the emphasized phrase (may be empty)


class BodyTeachingSlide(BaseModel):
    """Room for 1-2 full sentences of actual teaching content — distinct from
    BodySlide's single emphasis fragment, which can't hold real substance.

    heading/body are the legacy chain's own two-field shape, unchanged.
    accent_phrase is the carousel direct-write port's field (task "#19"),
    added on top rather than replacing anything here, since this model is
    shared with legacy (generator.py::_build_slide) -- direct-write hardcodes
    heading to "" and supplies accent_phrase (an exact substring of body, for
    in-line emphasis); legacy leaves accent_phrase ""."""

    template_id: Literal["carousel_body_teaching"] = "carousel_body_teaching"
    heading: str    # legacy: a short lead-in label or phrase. Direct-write: always ""
    body: str        # the actual teaching content / retold beat
    accent_phrase: str = ""  # direct-write only: exact substring of body to render emphasized. Always "" for legacy


class ClosingSlide(BaseModel):
    """logbook #39, round 8: cta/handle moved to ConversationSlide, the true
    last slide as of round 7 — they were still landing here as a leftover from
    before ConversationSlide existed. signature ("with you,") stays a real,
    computed field (hardcoded in _build_slide, never brand_kit-driven) but is
    no longer rendered by the frontend template — display-only removal, same
    pattern as #32's masthead simplification: the backend value is unchanged,
    only CarouselClosing.tsx stops drawing it."""

    template_id: Literal["carousel_closing"] = "carousel_closing"
    takeaway: str          # the only LLM-authored field on this slide
    signature: str = "with you,"


class ConversationSlide(BaseModel):
    """First structural (not prompt-only) change in the #39 v1 line of work
    (logbook #39, round 7) — the real CTA/question slide, matching the locked
    hand-written v1 reference format. Carousel-only, appended after
    carousel_closing — now the true last slide, so cta/handle (round 8) moved
    here from ClosingSlide, where they were a leftover from before this slide
    existed. label, invite, cta, and handle are all fixed brand copy, not
    model-generated (same pattern as ClosingSlide.signature) — only question
    is ever asked of the model.

    label originally used a leading emoji; verified via real Satori renders that
    this project's bundled Inter TTF has no glyph for it (nor for em dash,
    middot, or hedera/star alternatives tried) -- all rendered as tofu. Plain
    ASCII hyphen confirmed rendering cleanly (logbook #39, glyph fix)."""

    template_id: Literal["carousel_conversation"] = "carousel_conversation"
    label: str = "- Conversation for today"
    question: str          # the only LLM-authored field on this slide
    invite: str = "I'd love to hear it."
    cta: str = ""
    handle: str = ""


class QuoteSlide(BaseModel):
    template_id: Literal["single_quote"] = "single_quote"
    quote: str


class StatSlide(BaseModel):
    template_id: Literal["single_stat"] = "single_stat"
    kicker: str
    number: str
    supporting_line: str


Slide = Annotated[
    Union[
        CoverSlide,
        BodySlide,
        BodyTeachingSlide,
        ClosingSlide,
        ConversationSlide,
        QuoteSlide,
        StatSlide,
    ],
    Field(discriminator="template_id"),
]


class GeneratedPost(BaseModel):
    slides: list[Slide]
    caption: str
    hashtags: list[str]
