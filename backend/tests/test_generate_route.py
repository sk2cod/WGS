import asyncio
import json
import random
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

_ANGLE_JSON = json.dumps({"angle": "a specific test angle", "mood": "bold"})
_DRAFT_CAROUSEL_JSON = json.dumps(
    {
        "slides": [
            {"headline_word": "PAUSE", "script_word": "first.", "kicker": "short kicker one"},
            {"statement_pre": "short body", "statement_script": "two", "statement_post": ""},
            {"takeaway": "short body three"},
        ],
        "caption": "a caption",
        "hashtags": ["#a", "#b"],
    }
)
_DRAFT_SINGLE_QUOTE_JSON = json.dumps(
    {"slides": [{"quote": "one punchy line"}], "caption": "a caption", "hashtags": ["#a"]}
)
_DRAFT_SINGLE_STAT_JSON = json.dumps(
    {
        "slides": [{"kicker": "Did you know", "number": "42%", "supporting_line": "one punchy line"}],
        "caption": "a caption",
        "hashtags": ["#a"],
    }
)


class _QueueLLM:
    def __init__(self, responses: list[str]):
        self._responses = list(responses)

    def complete(self, *, tier, system, prompt, max_tokens, cache=True):
        return self._responses.pop(0)


class _FakeImage:
    def __init__(self):
        self.call_count = 0

    def generate(self, *, prompt, size, quality):
        self.call_count += 1
        buf = BytesIO()
        Image.new("RGB", (10, 10), color=(120, 120, 120)).save(buf, format="PNG")
        return buf.getvalue()


def _settings(**overrides) -> Settings:
    values = {"enable_critique": False, "image_quality": "low", "image_size": "1024x1536"}
    values.update(overrides)
    return Settings(**values)


def _single_image_draft_for_seed(topic_id: str, seed: int) -> str:
    """Slide shape for a single-image post depends on the (randomly sampled) approach's
    voice register — sample with the same seed the test will pass to run_generate so
    the canned draft JSON matches whatever role actually gets requested."""
    topic = get_topics_by_id()[topic_id]
    _, approach, _ = sample_cell(topic, [], rng=random.Random(seed))
    register = APPROACH_REGISTER[approach.value]
    return _DRAFT_SINGLE_QUOTE_JSON if register == "poetic" else _DRAFT_SINGLE_STAT_JSON


@pytest.fixture(autouse=True)
def _isolated_hero_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(duotone_module, "CACHE_DIR", tmp_path / "heroes")


def test_run_generate_carousel_returns_hero_and_writes_memory(tmp_path):
    store = MemoryStore(path=tmp_path / "memory.json")
    llm = _QueueLLM([_ANGLE_JSON, _DRAFT_CAROUSEL_JSON])
    image = _FakeImage()

    result = asyncio.run(
        run_generate(
            topic_id="mindset-reframing-self-doubt",
            format=Format.CAROUSEL,
            brand_kit=WGS_BRAND_KIT,
            topics_by_id=get_topics_by_id(),
            store=store,
            llm=llm,
            image=image,
            settings=_settings(),
        )
    )

    assert len(result.post.slides) == 3
    assert result.post.slides[0].template_id == "carousel_cover"
    assert result.brief.mood == "bold"
    assert result.brief.angle == "a specific test angle"
    assert result.hero_image_base64 is not None
    assert result.validation_errors == []
    assert image.call_count == 1

    records = store.load()
    assert len(records) == 1
    assert records[0].topic_id == "mindset-reframing-self-doubt"
    assert records[0].status == "draft"


def test_run_generate_single_image_skips_hero_entirely(tmp_path):
    store = MemoryStore(path=tmp_path / "memory.json")
    seed = 0
    draft_json = _single_image_draft_for_seed("mindset-reframing-self-doubt", seed)
    llm = _QueueLLM([_ANGLE_JSON, draft_json])
    image = _FakeImage()

    result = asyncio.run(
        run_generate(
            topic_id="mindset-reframing-self-doubt",
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


def test_run_generate_reruns_of_same_topic_yield_different_angle(tmp_path):
    store = MemoryStore(path=tmp_path / "memory.json")
    angle_1 = json.dumps({"angle": "angle one", "mood": "wisdom"})
    angle_2 = json.dumps({"angle": "angle two", "mood": "wisdom"})
    llm = _QueueLLM([angle_1, _DRAFT_CAROUSEL_JSON, angle_2, _DRAFT_CAROUSEL_JSON])
    image = _FakeImage()

    kwargs = dict(
        topic_id="mindset-reframing-self-doubt",
        format=Format.CAROUSEL,
        brand_kit=WGS_BRAND_KIT,
        topics_by_id=get_topics_by_id(),
        store=store,
        llm=llm,
        image=image,
        settings=_settings(),
    )
    first = asyncio.run(run_generate(**kwargs))
    second = asyncio.run(run_generate(**kwargs))

    assert first.brief.angle != second.brief.angle
    assert len(store.load()) == 2


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
