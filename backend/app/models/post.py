"""Per-template slide content — mirrors frontend/lib/types.ts exactly (the render
contract, Section 8 of implementation-guide.md), so a slide the backend generates
needs no lossy reshaping before /api/render can draw it. `template_id` is a real
discriminator: the frontend uses the same field to pick which component and which
render call to make."""

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

SlideRole = Literal["carousel_cover", "carousel_body", "carousel_closing", "single_quote", "single_stat"]


class CoverSlide(BaseModel):
    template_id: Literal["carousel_cover"] = "carousel_cover"
    headline_word: str    # one bold structural word, e.g. "PAUSE"
    script_word: str      # one short script-accent phrase, e.g. "first."
    kicker: str            # one supporting line


class BodySlide(BaseModel):
    template_id: Literal["carousel_body"] = "carousel_body"
    statement_pre: str     # words before the emphasized phrase (may be empty)
    statement_script: str  # exactly one emphasized phrase, script font
    statement_post: str    # words after the emphasized phrase (may be empty)


class ClosingSlide(BaseModel):
    template_id: Literal["carousel_closing"] = "carousel_closing"
    takeaway: str          # the only LLM-authored field on this slide
    signature: str = "with you,"
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
    Union[CoverSlide, BodySlide, ClosingSlide, QuoteSlide, StatSlide],
    Field(discriminator="template_id"),
]


class GeneratedPost(BaseModel):
    slides: list[Slide]
    caption: str
    hashtags: list[str]
