"""Paste-a-link: fetch -> extract -> brief with the article pinned as the only
citable source. Generated as reporting-with-attribution, never assertion (blueprint
Section 10) — requires_citation is always True here, and the only source is the
article itself."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import trafilatura

from app.engine.brief_builder import BriefResult
from app.models.brand_kit import BrandKit
from app.models.brief import ContentBrief, Source
from app.models.enums import Approach, Format
from app.models.memory import MemoryRecord, next_masthead_number
from app.taxonomy.voice_register import APPROACH_REGISTER

_SLIDE_COUNT = {Format.CAROUSEL: 3, Format.SINGLE_IMAGE: 1}


class PasteLinkError(Exception):
    """A pasted URL couldn't be fetched, or had no extractable article text."""


def extract_source(url: str) -> Source:
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        raise PasteLinkError(f"could not fetch {url!r}")

    text = trafilatura.extract(downloaded)
    if not text:
        raise PasteLinkError(f"could not extract article text from {url!r}")

    metadata = trafilatura.extract_metadata(downloaded, default_url=url)
    title = (metadata.title if metadata else None) or url
    author = metadata.author if metadata else None

    return Source(
        title=title,
        author=author,
        url=url,
        excerpt=text,
        retrieved_at=datetime.now(timezone.utc),
    )


def build_paste_link_brief(
    source: Source,
    brand_kit: BrandKit,
    memory: list[MemoryRecord],
    *,
    format: Format = Format.CAROUSEL,
    approach: Approach = Approach.STAT_RESEARCH,
    mood: str = "wisdom",
    category: str = "Society",
    goal: str = "inform",
) -> BriefResult:
    register = APPROACH_REGISTER[approach.value]
    brand_voice_samples = list(getattr(brand_kit.voice_samples, register))
    topic_id = f"paste-link:{hashlib.sha256((source.url or source.title).encode()).hexdigest()[:12]}"

    brief = ContentBrief(
        topic_id=topic_id,
        topic_name=source.title,
        angle=f"reporting on: {source.title}",
        approach=approach,
        goal=goal,
        mood=mood,
        format=format,
        slide_count=_SLIDE_COUNT[format],
        tone=brand_kit.default_tone,
        brand_voice_samples=brand_voice_samples,
        signature_cta=brand_kit.signature_cta,
        requires_citation=True,
        sensitivity="normal",
        sources=[source],
        hero_image_prompt=(
            f"Abstract, editorial, textural image evoking '{source.title}' — "
            f"no literal faces or text, {mood} mood."
        ),
    )

    masthead_number = next_masthead_number(category, memory)
    return BriefResult(brief=brief, masthead=f"{brand_kit.masthead_short} — {masthead_number}")
