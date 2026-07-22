"""POST /generate — a brief in, a validated post out. Text and image lanes run in
parallel off the same brief (blueprint Section 15): reshuffle-image only ever reruns
the image lane, and single-image posts never pay for a hero at all (Section 12 — only
the carousel cover template carries a photo).

No brief/post persistence exists yet (Supabase lands in Phase 6), so the client holds
the full `ContentBrief` + `GeneratedPost` for the duration of one editing session and
passes them back on `/generate/regenerate-slide` and `/generate/reshuffle-image` —
the same "Python owns the brief" pattern as everywhere else, just round-tripped
through the client instead of a database.

`/generate/from-brief` exists for briefs that don't come from the taxonomy at all —
paste-a-link (Section 10) builds a `ContentBrief` whose `topic_id` isn't a real Topic,
so it can't flow through `/generate`'s topic lookup; it runs the exact same generation
lane against whatever brief it's handed instead."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import random
import uuid
from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.engine.angle_engine import (
    SampledAngle,
    SingleImageStyle,
    assemble_carousel_context,
    generate_angle,
)
from app.engine.brief_builder import _hero_image_prompt, build_brief
from app.engine.generator import draft_carousel_direct, generate_post, regenerate_slide, slide_text
from app.engine.memory import MemoryStore
from app.engine.validator import validate_post
from app.models.brand_kit import BrandKit, MoodPalette
from app.models.brief import ContentBrief
from app.models.enums import Approach, EntryPoint, Format
from app.models.memory import MemoryRecord
from app.models.post import GeneratedPost, Slide
from app.models.topic import Topic
from app.providers.duotone import duotone_and_cache, get_cached_hero
from app.providers.image import ImageProvider
from app.providers.llm import LLMProvider
from app.taxonomy.loader import get_topics_by_id
from app.taxonomy.wgs_brand_kit import get_brand_kit

router = APIRouter()


class ProposeRequest(BaseModel):
    topic_id: str
    format: Format
    # "Poetic Quote" / "Quick Stat" (logbook #28) — ignored unless format is
    # single_image; leaving it unset samples from the full 4-approach safe pool,
    # same as before this field existed.
    single_image_style: SingleImageStyle | None = None


class ProposeResponse(BaseModel):
    topic_id: str
    topic_name: str
    angle: str
    approach: Approach
    mood: str
    reason: str
    visual_subject: str
    fingerprint: str


class GenerateRequest(BaseModel):
    topic_id: str
    format: Format
    goal: str = "educate"
    # if set (all five together, as returned by /generate/propose), the already-shown
    # proposal is honored as-is rather than sampling a fresh one — so what she accepted
    # is what she gets, not a different roll of the angle engine.
    angle: str | None = None
    approach: Approach | None = None
    mood: str | None = None
    visual_subject: str | None = None
    fingerprint: str | None = None
    # Only takes effect when the above five are unset (a fresh sample, not a preselected
    # replay) and format is single_image — see ProposeRequest.single_image_style.
    single_image_style: SingleImageStyle | None = None


class GenerateFromBriefRequest(BaseModel):
    brief: ContentBrief
    masthead: str
    category: str = "Society"


class GenerateResponse(BaseModel):
    brief: ContentBrief
    post: GeneratedPost
    masthead: str
    hero_image_base64: str | None = None
    validation_errors: list[str] = []
    # The MemoryRecord's id (logbook #35) -- generated server-side in
    # _generate_for_brief below and always persisted, but previously discarded
    # rather than returned. routes/export.py's confirm endpoint needs it to know
    # which draft record a given editor session is confirming.
    memory_id: str


class RegenerateSlideRequest(BaseModel):
    brief: ContentBrief
    post: GeneratedPost
    slide_index: int


class RegenerateSlideResponse(BaseModel):
    slide: Slide


class ReshuffleImageRequest(BaseModel):
    brief: ContentBrief
    variant: int = 1


class ReshuffleImageResponse(BaseModel):
    hero_image_base64: str


def _hero_cache_keyword(brief: ContentBrief, *, variant: int | None = None) -> str:
    """Cache keyword for a brief's hero image: topic_id (namespacing/readability) plus
    a short hash of hero_image_prompt (logbook #30) — hero_image_prompt is built from
    visual_subject (or angle as a fallback, logbook #4), so it varies whenever the
    actual visual content of the post does. Before this, the keyword was topic_id
    alone, so any two posts on the same topic+mood silently shared one cached image
    regardless of how different their angles were.

    `variant` is reshuffle-image's escape hatch (routes below): each explicit variant
    number gets its own cache entry, so repeated taps of "reshuffle" keep generating
    fresh images, while re-requesting the same variant number is still a free cache
    hit — unchanged behavior, just now scoped per-angle instead of per-topic."""
    content_key = hashlib.sha256(brief.hero_image_prompt.encode()).hexdigest()[:16]
    base = f"{brief.topic_id}:{content_key}"
    return f"{base}:v{variant}" if variant is not None else base


def _generate_hero_for_keyword(
    hero_image_prompt: str,
    keyword: str,
    palette: MoodPalette,
    image: ImageProvider,
    settings: Settings,
) -> bytes:
    cached = get_cached_hero(keyword, palette.primary, palette.secondary)
    if cached is not None:
        return cached
    raw = image.generate(
        prompt=hero_image_prompt, size=settings.image_size, quality=settings.image_quality
    )
    return duotone_and_cache(raw, keyword, palette.primary, palette.secondary)


def _generate_hero(
    brief: ContentBrief, brand_kit: BrandKit, image: ImageProvider, settings: Settings
) -> bytes:
    """Carousel cover only. Cached by topic + angle content + mood palette — a cache
    hit skips the image API call entirely."""
    palette = brand_kit.mood_palettes[brief.mood]
    keyword = _hero_cache_keyword(brief)
    return _generate_hero_for_keyword(brief.hero_image_prompt, keyword, palette, image, settings)


def _finalize_generation(
    brief: ContentBrief,
    post: GeneratedPost,
    hero_bytes: bytes | None,
    *,
    brand_kit: BrandKit,
    store: MemoryStore,
    memory: list[MemoryRecord],
    fingerprint: str,
    category: str,
    masthead: str,
    anchor: str = "",
) -> GenerateResponse:
    """Shared tail for both the legacy chain and the carousel direct-write
    port (logbook #43-46): validate, write the memory record, build the
    response. `anchor` (logbook #43) is empty for every path except carousel
    direct-write, which has a real one to record -- single_image and the
    legacy carousel chain have no equivalent concept."""
    validation = validate_post(brief, brand_kit, post, memory, fingerprint)

    record = MemoryRecord(
        id=str(uuid.uuid4()),
        date=date.today(),
        topic_id=brief.topic_id,
        category=category,
        angle=brief.angle,
        approach=brief.approach,
        format=brief.format,
        mood=brief.mood,
        hook=slide_text(post.slides[0])[:80] if post.slides else post.caption[:80],
        fingerprint=fingerprint,
        source_ids=[],
        status="draft",
        anchor=anchor,
    )
    store.append(record)

    return GenerateResponse(
        brief=brief,
        post=post,
        masthead=masthead,
        hero_image_base64=base64.b64encode(hero_bytes).decode("ascii") if hero_bytes else None,
        validation_errors=validation.errors,
        memory_id=record.id,
    )


async def _generate_for_brief(
    brief: ContentBrief,
    *,
    brand_kit: BrandKit,
    llm: LLMProvider,
    image: ImageProvider,
    settings: Settings,
    store: MemoryStore,
    memory: list[MemoryRecord],
    fingerprint: str,
    category: str,
    masthead: str,
) -> GenerateResponse:
    text_task = asyncio.to_thread(
        generate_post, brief, brand_kit, llm, enable_critique=settings.enable_critique
    )
    if brief.format == Format.CAROUSEL:
        image_task = asyncio.to_thread(_generate_hero, brief, brand_kit, image, settings)
        post, hero_bytes = await asyncio.gather(text_task, image_task)
    else:
        post = await text_task
        hero_bytes = None

    return _finalize_generation(
        brief,
        post,
        hero_bytes,
        brand_kit=brand_kit,
        store=store,
        memory=memory,
        fingerprint=fingerprint,
        category=category,
        masthead=masthead,
    )


async def _generate_carousel_direct(
    *,
    topic: Topic,
    goal: str,
    topics_by_id: dict[str, Topic],
    brand_kit: BrandKit,
    memory: list[MemoryRecord],
    llm: LLMProvider,
    image: ImageProvider,
    settings: Settings,
    store: MemoryStore,
) -> GenerateResponse:
    """Carousel direct-write port (docs/logbook.md #43-46), wired in behind
    CAROUSEL_WRITER=direct_write. Sequential, not parallel, unlike
    _generate_for_brief's carousel branch above -- mood/visual_subject
    aren't known until the single writer call returns, so hero image
    generation can't start until after it. The legacy chain's cheap-tier
    generate_angle() call already knows mood/visual_subject before the
    strong-tier draft even starts, so its hero image runs in parallel with
    the text. This makes a direct-write carousel generation slower
    end-to-end than legacy, not faster -- a real tradeoff of this design, not
    a regression introduced by wiring it in."""
    context = assemble_carousel_context(topic, memory)
    # Provisional brief (logbook #43): angle/mood are placeholders here,
    # corrected below once the writer call returns them. requires_citation/
    # sources/knowledge_hints/format are real and already usable as-is.
    brief_result = build_brief(
        topic_id=topic.id,
        topics_by_id=topics_by_id,
        angle="(direct-write: pending, corrected after the writer call)",
        approach=Approach.STORY,
        mood="wisdom",
        format=Format.CAROUSEL,
        brand_kit=brand_kit,
        memory=memory,
        goal=goal,
    )
    provisional_brief = brief_result.brief

    post, anchor, mood, visual_subject = await asyncio.to_thread(
        draft_carousel_direct, provisional_brief, brand_kit, llm, topic, context
    )
    # Reused, not rebuilt (logbook #45) -- the exact same function
    # generate_angle()'s own visual_subject is already wrapped through via
    # build_brief().
    hero_image_prompt = _hero_image_prompt(visual_subject, mood)
    brief = provisional_brief.model_copy(
        update={"angle": anchor, "mood": mood, "hero_image_prompt": hero_image_prompt}
    )

    hero_bytes = await asyncio.to_thread(_generate_hero, brief, brand_kit, image, settings)
    # topic_id:anchor (logbook #43) -- the analog of the legacy chain's
    # topic_id:sub_concept:approach fingerprint, now that anchor, not
    # sub-concept, is the thing that shouldn't repeat on this path.
    fingerprint = f"{topic.id}:{anchor}"

    return _finalize_generation(
        brief,
        post,
        hero_bytes,
        brand_kit=brand_kit,
        store=store,
        memory=memory,
        fingerprint=fingerprint,
        category=topic.primary_category,
        masthead=brief_result.masthead,
        anchor=anchor,
    )


async def run_generate(
    *,
    topic_id: str,
    format: Format,
    goal: str = "educate",
    brand_kit: BrandKit,
    topics_by_id: dict[str, Topic],
    store: MemoryStore,
    llm: LLMProvider,
    image: ImageProvider,
    settings: Settings,
    rng: random.Random | None = None,
    preselected: SampledAngle | None = None,
    single_image_style: SingleImageStyle | None = None,
) -> GenerateResponse:
    topic = topics_by_id.get(topic_id)
    if topic is None:
        raise KeyError(f"Unknown topic_id: {topic_id!r}")

    memory = store.load()

    # Carousel direct-write port (logbook #43-46), default --
    # CAROUSEL_WRITER=legacy is the opt-in fallback to the original chain
    # below, same escape-hatch pattern as LLM_PROVIDER. Only ever applies to
    # a fresh sample: `preselected` means the client already saw and
    # accepted a real sample_cell-driven angle (via /generate/propose, or a
    # daily pick's precomputed hook/thumbnail) -- a concept the direct-write
    # path has no equivalent for, since one call decides everything at once
    # with nothing to preview first. Honoring a preselected angle always
    # uses the legacy chain regardless of this setting. single_image is
    # completely unaffected either way -- it never reaches this branch.
    if (
        format == Format.CAROUSEL
        and preselected is None
        and settings.carousel_writer == "direct_write"
    ):
        return await _generate_carousel_direct(
            topic=topic,
            goal=goal,
            topics_by_id=topics_by_id,
            brand_kit=brand_kit,
            memory=memory,
            llm=llm,
            image=image,
            settings=settings,
            store=store,
        )

    sampled = (
        preselected
        if preselected is not None
        else generate_angle(topic, memory, llm, format=format, single_image_style=single_image_style, rng=rng)
    )

    brief_result = build_brief(
        topic_id=topic.id,
        topics_by_id=topics_by_id,
        angle=sampled.angle,
        approach=sampled.approach,
        mood=sampled.mood,
        format=format,
        brand_kit=brand_kit,
        memory=memory,
        goal=goal,
        visual_subject=sampled.visual_subject,
    )

    return await _generate_for_brief(
        brief_result.brief,
        brand_kit=brand_kit,
        llm=llm,
        image=image,
        settings=settings,
        store=store,
        memory=memory,
        fingerprint=sampled.fingerprint,
        category=topic.primary_category,
        masthead=brief_result.masthead,
    )


@router.post("/generate/propose", response_model=ProposeResponse)
async def propose(request: ProposeRequest) -> ProposeResponse:
    """Cheap-tier preview: the angle engine's pick + a one-line reason, shown before
    committing to the expensive strong-tier text + image generation. 'Swipe to
    alternatives' is just calling this again — stateless, and cheap enough not to
    ration."""
    topic = get_topics_by_id().get(request.topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail=f"Unknown topic_id: {request.topic_id!r}")

    memory = MemoryStore().load()
    sampled = await asyncio.to_thread(
        generate_angle,
        topic,
        memory,
        LLMProvider(),
        format=request.format,
        single_image_style=request.single_image_style,
    )
    return ProposeResponse(
        topic_id=topic.id,
        topic_name=topic.name,
        angle=sampled.angle,
        approach=sampled.approach,
        mood=sampled.mood,
        reason=sampled.reason,
        visual_subject=sampled.visual_subject,
        fingerprint=sampled.fingerprint,
    )


@router.post("/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest) -> GenerateResponse:
    preselected = None
    if None not in (
        request.angle,
        request.approach,
        request.mood,
        request.visual_subject,
        request.fingerprint,
    ):
        preselected = SampledAngle(
            sub_concept="",
            approach=request.approach,  # type: ignore[arg-type]
            entry_point=EntryPoint.A_QUESTION,
            angle=request.angle,  # type: ignore[arg-type]
            mood=request.mood,  # type: ignore[arg-type]
            reason="",
            visual_subject=request.visual_subject,  # type: ignore[arg-type]
            fingerprint=request.fingerprint,  # type: ignore[arg-type]
        )

    try:
        return await run_generate(
            topic_id=request.topic_id,
            format=request.format,
            goal=request.goal,
            brand_kit=get_brand_kit(),
            topics_by_id=get_topics_by_id(),
            store=MemoryStore(),
            llm=LLMProvider(),
            image=ImageProvider(),
            settings=get_settings(),
            preselected=preselected,
            single_image_style=request.single_image_style,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/generate/from-brief", response_model=GenerateResponse)
async def generate_from_brief(request: GenerateFromBriefRequest) -> GenerateResponse:
    store = MemoryStore()
    brief = request.brief
    fingerprint = f"{brief.topic_id}:{brief.angle}:{brief.approach.value}"
    return await _generate_for_brief(
        brief,
        brand_kit=get_brand_kit(),
        llm=LLMProvider(),
        image=ImageProvider(),
        settings=get_settings(),
        store=store,
        memory=store.load(),
        fingerprint=fingerprint,
        category=request.category,
        masthead=request.masthead,
    )


@router.post("/generate/regenerate-slide", response_model=RegenerateSlideResponse)
async def regenerate_slide_route(request: RegenerateSlideRequest) -> RegenerateSlideResponse:
    try:
        slide = await asyncio.to_thread(
            regenerate_slide,
            request.brief,
            get_brand_kit(),
            request.post,
            request.slide_index,
            LLMProvider(),
        )
    except IndexError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RegenerateSlideResponse(slide=slide)


@router.post("/generate/reshuffle-image", response_model=ReshuffleImageResponse)
async def reshuffle_image_route(request: ReshuffleImageRequest) -> ReshuffleImageResponse:
    if request.brief.format != Format.CAROUSEL:
        raise HTTPException(status_code=400, detail="only the carousel cover has a hero image")

    settings = get_settings()
    palette = get_brand_kit().mood_palettes[request.brief.mood]
    keyword = _hero_cache_keyword(request.brief, variant=request.variant)
    hero_bytes = await asyncio.to_thread(
        _generate_hero_for_keyword,
        request.brief.hero_image_prompt,
        keyword,
        palette,
        ImageProvider(),
        settings,
    )
    return ReshuffleImageResponse(hero_image_base64=base64.b64encode(hero_bytes).decode("ascii"))
