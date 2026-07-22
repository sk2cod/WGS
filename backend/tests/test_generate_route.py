import asyncio
import json
import random
import re
from io import BytesIO

import pytest
from PIL import Image

import app.providers.duotone as duotone_module
from app.config import Settings
from app.engine.angle_engine import sample_cell
from app.engine.memory import MemoryStore
from app.models.enums import Format
from app.routes.generate import run_generate
from app.taxonomy.loader import get_topics_by_id
from app.taxonomy.voice_register import APPROACH_REGISTER
from app.taxonomy.wgs_brand_kit import WGS_BRAND_KIT

_DRAFT_SINGLE_QUOTE_JSON = json.dumps(
    {"slides": [{"quote": "one punchy line"}], "caption": "a caption", "hashtags": ["#a"]}
)
_DRAFT_SINGLE_STAT_JSON = json.dumps(
    {
        "slides": [{
            "kicker": "Did you know",
            "number": "42%",
            "supporting_line": (
                "One punchy line was never going to be enough content to fill "
                "this slide comfortably on its own"
            ),
        }],
        "caption": "a caption",
        "hashtags": ["#a"],
    }
)

# Placeholder content per possible carousel body-slot role — which role(s) actually
# get requested depends on the (randomly sampled) approach, so carousel drafts are
# generated adaptively (see _AdaptiveLLM) rather than as one fixed fragment/count.
# Word counts here are deliberately inside each role's real per-template range
# (generator.py::_WORD_RANGE_FOR_ROLE) — validate_post now enforces a floor as
# well as a ceiling per template, not just one flat max.
_SLIDE_CONTENT_BY_ROLE = {
    "carousel_cover": {"headline_word": "PAUSE", "script_word": "first.", "kicker": "short kicker"},
    "carousel_body": {
        "statement_pre": "This is a fuller short body statement",
        "statement_script": "that actually fills",
        "statement_post": "the space properly now",
    },
    "carousel_body_teaching": {
        "heading": "A heading",
        "body": (
            "A full sentence of teaching content that actually fills this slide "
            "with enough real substance to look intentional rather than sparse "
            "when it renders on the canvas, the way a real teaching slide is "
            "supposed to look in production."
        ),
    },
    "carousel_closing": {"takeaway": "Short body three words alone were never going to look complete"},
    # logbook #39 round 7 -- label/invite are fixed defaults, only question is asked
    "carousel_conversation": {
        "question": "What would you tell a friend who was standing exactly in your position right now?"
    },
}


class _QueueLLM:
    def __init__(self, responses: list[str]):
        self._responses = list(responses)

    def complete(self, *, tier, system, prompt, max_tokens, cache=True):
        return self._responses.pop(0)


class _AdaptiveCarouselLLM:
    """Returns canned cheap-tier (angle) responses in order, and for strong-tier
    (draft) calls, builds a slide list matching whatever roles the system prompt
    actually asked for — robust to whichever approach the angle engine samples."""

    def __init__(self, angle_responses: list[str]):
        self._angle_responses = list(angle_responses)

    def complete(self, *, tier, system, prompt, max_tokens, cache=True):
        if tier == "cheap":
            return self._angle_responses.pop(0)
        roles = re.findall(r"Slide \d+ \((\w+)\)", system)
        slides = [_SLIDE_CONTENT_BY_ROLE[r] for r in roles]
        return json.dumps({"slides": slides, "caption": "a caption", "hashtags": ["#a", "#b"]})


class _FakeImage:
    def __init__(self):
        self.call_count = 0

    def generate(self, *, prompt, size, quality):
        self.call_count += 1
        buf = BytesIO()
        Image.new("RGB", (10, 10), color=(120, 120, 120)).save(buf, format="PNG")
        return buf.getvalue()


def _direct_write_response_json(anchor: str) -> str:
    """One real direct-write JSON response (logbook #43-46) -- word counts
    sized inside carousel_body_teaching's real 35-50 range and
    closing/conversation's real ranges, matching the actual writer's schema,
    not the legacy chain's."""
    body_text = (
        "This is a full retold beat with enough real words to satisfy the "
        "teaching body role's much higher floor, since a carousel_body_teaching "
        "slide needs closer to two full sentences of real content."
    )
    return json.dumps({
        "anchor": anchor,
        "mood": "wisdom",
        "visual_subject": "a folded paper on a wooden table",
        "caption": "a caption",
        "headline_word": "PAUSE",
        "script_word": "first.",
        "kicker": "short kicker",
        "body_1_heading": "A heading",
        "body_1_text": body_text,
        "body_2_heading": "A heading",
        "body_2_text": body_text,
        "body_3_heading": "A heading",
        "body_3_text": body_text,
        "closing_takeaway": "Short body words alone were never going to look complete here",
        "conversation_question": "What would you tell a friend who was standing exactly in your position right now?",
        "hashtags": ["#a", "#b"],
    })


def _settings(**overrides) -> Settings:
    values = {"enable_critique": False, "image_quality": "low", "image_size": "1024x1536"}
    values.update(overrides)
    return Settings(**values)


def _single_image_draft_for_seed(topic_id: str, seed: int) -> str:
    """Slide shape for a single-image post depends on the (randomly sampled) approach's
    voice register — sample with the same seed the test will pass to run_generate so
    the canned draft JSON matches whatever role actually gets requested."""
    topic = get_topics_by_id()[topic_id]
    _, approach, _ = sample_cell(topic, [], format=Format.SINGLE_IMAGE, rng=random.Random(seed))
    register = APPROACH_REGISTER[approach.value]
    return _DRAFT_SINGLE_QUOTE_JSON if register == "poetic" else _DRAFT_SINGLE_STAT_JSON


@pytest.fixture(autouse=True)
def _isolated_hero_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(duotone_module, "CACHE_DIR", tmp_path / "heroes")


def test_run_generate_carousel_legacy_returns_hero_and_writes_memory(tmp_path):
    """legacy chain explicitly (CAROUSEL_WRITER=legacy) -- direct_write is
    now the default (logbook #46), covered separately below."""
    store = MemoryStore(path=tmp_path / "memory.json")
    llm = _AdaptiveCarouselLLM([json.dumps({"angle": "a specific test angle", "mood": "bold"})])
    image = _FakeImage()

    result = asyncio.run(
        run_generate(
            topic_id="mindset-self-doubt",
            format=Format.CAROUSEL,
            brand_kit=WGS_BRAND_KIT,
            topics_by_id=get_topics_by_id(),
            store=store,
            llm=llm,
            image=image,
            settings=_settings(carousel_writer="legacy"),
        )
    )

    assert result.post.slides[0].template_id == "carousel_cover"
    assert result.post.slides[-1].template_id == "carousel_conversation"
    assert result.brief.mood == "bold"
    assert result.brief.angle == "a specific test angle"
    assert result.hero_image_base64 is not None
    assert result.validation_errors == []
    assert image.call_count == 1

    records = store.load()
    assert len(records) == 1
    assert records[0].topic_id == "mindset-self-doubt"
    assert records[0].status == "draft"


def test_run_generate_single_image_skips_hero_entirely(tmp_path):
    store = MemoryStore(path=tmp_path / "memory.json")
    seed = 0
    draft_json = _single_image_draft_for_seed("mindset-self-doubt", seed)
    llm = _QueueLLM([json.dumps({"angle": "a specific test angle", "mood": "bold"}), draft_json])
    image = _FakeImage()

    result = asyncio.run(
        run_generate(
            topic_id="mindset-self-doubt",
            format=Format.SINGLE_IMAGE,
            brand_kit=WGS_BRAND_KIT,
            topics_by_id=get_topics_by_id(),
            store=store,
            llm=llm,
            image=image,
            settings=_settings(),
            rng=random.Random(seed),
        )
    )

    assert result.hero_image_base64 is None
    assert image.call_count == 0
    assert len(result.post.slides) == 1


def test_run_generate_legacy_reruns_of_same_topic_yield_different_angle(tmp_path):
    """legacy chain explicitly -- see note on the test above."""
    store = MemoryStore(path=tmp_path / "memory.json")
    angle_1 = json.dumps({"angle": "angle one", "mood": "wisdom"})
    angle_2 = json.dumps({"angle": "angle two", "mood": "wisdom"})
    llm = _AdaptiveCarouselLLM([angle_1, angle_2])
    image = _FakeImage()

    kwargs = dict(
        topic_id="mindset-self-doubt",
        format=Format.CAROUSEL,
        brand_kit=WGS_BRAND_KIT,
        topics_by_id=get_topics_by_id(),
        store=store,
        llm=llm,
        image=image,
        settings=_settings(carousel_writer="legacy"),
    )
    first = asyncio.run(run_generate(**kwargs))
    second = asyncio.run(run_generate(**kwargs))

    assert first.brief.angle != second.brief.angle
    assert len(store.load()) == 2


def test_run_generate_carousel_direct_write_is_the_default(tmp_path):
    """CAROUSEL_WRITER=direct_write is the default as of logbook #46 -- a
    fresh (non-preselected) carousel request with no explicit override
    routes through draft_carousel_direct, not the legacy chain. Confirmed by
    the single-call LLM queue: the legacy chain would need a second
    (cheap-tier) response for generate_angle and would fail with an empty
    queue if it were reached."""
    store = MemoryStore(path=tmp_path / "memory.json")
    llm = _QueueLLM([_direct_write_response_json("a real test anchor")])
    image = _FakeImage()

    result = asyncio.run(
        run_generate(
            topic_id="mindset-self-doubt",
            format=Format.CAROUSEL,
            brand_kit=WGS_BRAND_KIT,
            topics_by_id=get_topics_by_id(),
            store=store,
            llm=llm,
            image=image,
            settings=_settings(),  # carousel_writer defaults to "direct_write"
        )
    )

    assert result.post.slides[0].template_id == "carousel_cover"
    assert result.post.slides[1].template_id == "carousel_body_teaching"
    assert result.post.slides[-1].template_id == "carousel_conversation"
    assert result.brief.angle == "a real test anchor"
    assert result.brief.mood == "wisdom"
    assert result.hero_image_base64 is not None
    assert image.call_count == 1

    records = store.load()
    assert len(records) == 1
    assert records[0].anchor == "a real test anchor"
    assert records[0].fingerprint == "mindset-self-doubt:a real test anchor"


def test_run_generate_carousel_legacy_override_still_works(tmp_path):
    """CAROUSEL_WRITER=legacy is the documented opt-in fallback -- confirms
    the escape hatch actually routes to the old chain, not just that the
    setting exists."""
    store = MemoryStore(path=tmp_path / "memory.json")
    llm = _AdaptiveCarouselLLM([json.dumps({"angle": "a legacy angle", "mood": "bold"})])
    image = _FakeImage()

    result = asyncio.run(
        run_generate(
            topic_id="mindset-self-doubt",
            format=Format.CAROUSEL,
            brand_kit=WGS_BRAND_KIT,
            topics_by_id=get_topics_by_id(),
            store=store,
            llm=llm,
            image=image,
            settings=_settings(carousel_writer="legacy"),
        )
    )

    assert result.brief.angle == "a legacy angle"
    records = store.load()
    assert records[0].anchor == ""  # legacy has no anchor concept


def test_run_generate_carousel_preselected_bypasses_direct_write(tmp_path):
    """A preselected angle (the /generate/propose round-trip, or a daily
    pick's precomputed hook/thumbnail) means the client already accepted a
    real sample_cell-driven angle -- direct_write has no equivalent to
    preview, so it must always defer to the legacy chain here regardless of
    CAROUSEL_WRITER. Confirmed by using an _AdaptiveCarouselLLM queue shaped
    for the legacy draft call, not the direct-write schema -- this would
    fail if the route incorrectly tried the direct-write path instead."""
    from app.engine.angle_engine import SampledAngle
    from app.models.enums import Approach, EntryPoint

    store = MemoryStore(path=tmp_path / "memory.json")
    llm = _AdaptiveCarouselLLM([])  # no angle call expected -- preselected skips generate_angle
    image = _FakeImage()
    preselected = SampledAngle(
        sub_concept="a sub concept",
        approach=Approach.QUESTION_REFLECTION,
        entry_point=EntryPoint.A_QUESTION,
        angle="the preselected angle",
        mood="wisdom",
        reason="",
        visual_subject="a visual subject",
        fingerprint="mindset-self-doubt:custom:question_reflection",
    )

    result = asyncio.run(
        run_generate(
            topic_id="mindset-self-doubt",
            format=Format.CAROUSEL,
            brand_kit=WGS_BRAND_KIT,
            topics_by_id=get_topics_by_id(),
            store=store,
            llm=llm,
            image=image,
            settings=_settings(),  # direct_write default -- must still be bypassed
            preselected=preselected,
        )
    )

    assert result.brief.angle == "the preselected angle"
    records = store.load()
    assert records[0].anchor == ""  # legacy path, no anchor concept


def test_run_generate_unknown_topic_raises_key_error(tmp_path):
    store = MemoryStore(path=tmp_path / "memory.json")

    with pytest.raises(KeyError):
        asyncio.run(
            run_generate(
                topic_id="does-not-exist",
                format=Format.CAROUSEL,
                brand_kit=WGS_BRAND_KIT,
                topics_by_id=get_topics_by_id(),
                store=store,
                llm=_QueueLLM([]),
                image=_FakeImage(),
                settings=_settings(),
            )
        )
