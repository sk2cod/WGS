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
import random
import uuid
from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.engine.angle_engine import SampledAngle, SingleImageStyle, generate_angle
from app.engine.brief_builder import build_brief
from app.engine.generator import generate_post, regenerate_slide, slide_text
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
    """Carousel cover only. Cached by topic keyword + mood palette — a cache hit skips
    the image API call entirely."""
    palette = brand_kit.mood_palettes[brief.mood]
    return _generate_hero_for_keyword(brief.hero_image_prompt, brief.topic_id, palette, image, settings)


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
    )
    store.append(record)

    return GenerateResponse(
        brief=brief,
        post=post,
        masthead=masthead,
        hero_image_base64=base64.b64encode(hero_bytes).decode("ascii") if hero_bytes else None,
        validation_errors=validation.errors,
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
    keyword = f"{request.brief.topic_id}:v{request.variant}"
    hero_bytes = await asyncio.to_thread(
        _generate_hero_for_keyword,
        request.brief.hero_image_prompt,
        keyword,
        palette,
        ImageProvider(),
        settings,
    )
    return ReshuffleImageResponse(hero_image_base64=base64.b64encode(hero_bytes).decode("ascii"))
