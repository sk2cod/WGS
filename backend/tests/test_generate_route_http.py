"""End-to-end route tests for POST /generate, /generate/regenerate-slide, and
/generate/reshuffle-image via FastAPI's TestClient — catches dependency-wiring bugs
that unit tests of run_generate/regenerate_slide can't see. LLMProvider/ImageProvider/
MemoryStore are monkeypatched at the route-module level so no real API call happens."""

import json
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

import app.providers.duotone as duotone_module
import app.routes.generate as generate_module
from app.config import Settings
from app.engine.memory import MemoryStore
from app.main import app
from app.taxonomy.wgs_brand_kit import WGS_BRAND_KIT

_ANGLE_JSON = json.dumps({"angle": "a specific test angle", "mood": "wisdom"})
# 4 slides: cover, body, closing, conversation (logbook #39 round 7 -- the first
# structural change in the v1 line of work; carousel_conversation is appended after
# closing for every carousel brief regardless of approach).
_DRAFT_CAROUSEL_JSON = json.dumps(
    {
        "slides": [
            {"headline_word": "PAUSE", "script_word": "first.", "kicker": "short kicker"},
            {"statement_pre": "short body", "statement_script": "two", "statement_post": ""},
            {"takeaway": "short body three"},
            {"question": "What would you tell a friend in your exact position?"},
        ],
        "caption": "a caption",
        "hashtags": ["#a", "#b"],
    }
)

# question_reflection isn't in TEACHING_BODY_APPROACHES, so a carousel using it gets
# the old 3-slide (cover/body/closing) shape above — used to force a deterministic
# slide count/shape in tests that are about route wiring, not approach-driven shape.
_NON_TEACHING_PRESELECTED = {
    "angle": "her exact accepted angle",
    "approach": "question_reflection",
    "mood": "wisdom",
    "visual_subject": "a sticky note reading 'not today' on a bathroom mirror",
    "fingerprint": "mindset-self-doubt:custom:question_reflection",
}


class _QueueLLM:
    def __init__(self, responses):
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


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(duotone_module, "CACHE_DIR", tmp_path / "heroes")
    monkeypatch.setattr(generate_module, "MemoryStore", lambda: MemoryStore(path=tmp_path / "memory.json"))
    monkeypatch.setattr(generate_module, "get_brand_kit", lambda: WGS_BRAND_KIT)
    # the real .env sets ENABLE_CRITIQUE=true; force it off so canned LLM responses
    # (angle + draft, no critique/refine) are the only calls each test needs to queue
    monkeypatch.setattr(
        generate_module,
        "get_settings",
        lambda: Settings(enable_critique=False, image_quality="low", image_size="1024x1536"),
    )


def test_generate_route_returns_full_brief_and_post(monkeypatch):
    monkeypatch.setattr(generate_module, "LLMProvider", lambda: _QueueLLM([_DRAFT_CAROUSEL_JSON]))
    monkeypatch.setattr(generate_module, "ImageProvider", _FakeImage)

    client = TestClient(app)
    response = client.post(
        "/generate",
        json={
            "topic_id": "mindset-self-doubt",
            "format": "carousel",
            **_NON_TEACHING_PRESELECTED,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["brief"]["topic_id"] == "mindset-self-doubt"
    assert len(body["post"]["slides"]) == 4
    assert body["post"]["slides"][0]["template_id"] == "carousel_cover"
    assert body["hero_image_base64"] is not None
    assert body["validation_errors"] == []


def test_generate_route_unknown_topic_returns_404(monkeypatch):
    monkeypatch.setattr(generate_module, "LLMProvider", lambda: _QueueLLM([]))
    monkeypatch.setattr(generate_module, "ImageProvider", _FakeImage)

    client = TestClient(app)
    response = client.post("/generate", json={"topic_id": "does-not-exist", "format": "carousel"})

    assert response.status_code == 404


def test_regenerate_slide_route_updates_one_slide(monkeypatch):
    monkeypatch.setattr(generate_module, "LLMProvider", lambda: _QueueLLM([_DRAFT_CAROUSEL_JSON]))
    monkeypatch.setattr(generate_module, "ImageProvider", _FakeImage)

    client = TestClient(app)
    generated = client.post(
        "/generate",
        json={
            "topic_id": "mindset-self-doubt",
            "format": "carousel",
            **_NON_TEACHING_PRESELECTED,
        },
    ).json()

    monkeypatch.setattr(
        generate_module,
        "LLMProvider",
        lambda: _QueueLLM(
            [json.dumps({"headline_word": "BREATHE", "script_word": "not react.", "kicker": "new"})]
        ),
    )
    response = client.post(
        "/generate/regenerate-slide",
        json={"brief": generated["brief"], "post": generated["post"], "slide_index": 0},
    )

    assert response.status_code == 200
    slide = response.json()["slide"]
    assert slide["template_id"] == "carousel_cover"
    assert slide["headline_word"] == "BREATHE"


def test_regenerate_slide_route_out_of_range_returns_400(monkeypatch):
    monkeypatch.setattr(generate_module, "LLMProvider", lambda: _QueueLLM([_DRAFT_CAROUSEL_JSON]))
    monkeypatch.setattr(generate_module, "ImageProvider", _FakeImage)

    client = TestClient(app)
    generated = client.post(
        "/generate",
        json={
            "topic_id": "mindset-self-doubt",
            "format": "carousel",
            **_NON_TEACHING_PRESELECTED,
        },
    ).json()

    monkeypatch.setattr(generate_module, "LLMProvider", lambda: _QueueLLM([]))
    response = client.post(
        "/generate/regenerate-slide",
        json={"brief": generated["brief"], "post": generated["post"], "slide_index": 99},
    )

    assert response.status_code == 400


def test_reshuffle_image_route_returns_new_hero_without_full_regenerate(monkeypatch):
    fake_image = _FakeImage()
    monkeypatch.setattr(generate_module, "LLMProvider", lambda: _QueueLLM([_DRAFT_CAROUSEL_JSON]))
    monkeypatch.setattr(generate_module, "ImageProvider", lambda: fake_image)

    client = TestClient(app)
    generated = client.post(
        "/generate",
        json={
            "topic_id": "mindset-self-doubt",
            "format": "carousel",
            **_NON_TEACHING_PRESELECTED,
        },
    ).json()
    assert fake_image.call_count == 1  # the initial cover generation

    response = client.post(
        "/generate/reshuffle-image", json={"brief": generated["brief"], "variant": 1}
    )

    assert response.status_code == 200
    assert response.json()["hero_image_base64"]
    assert fake_image.call_count == 2  # a fresh image, not a cache hit on the cover keyword


def test_propose_route_returns_angle_approach_and_reason(monkeypatch):
    monkeypatch.setattr(
        generate_module,
        "LLMProvider",
        lambda: _QueueLLM(
            [
                json.dumps(
                    {
                        "angle": "a proposed angle",
                        "mood": "bold",
                        "reason": "because it's punchy",
                        "visual_subject": "a torn-up to-do list on a kitchen counter",
                    }
                )
            ]
        ),
    )

    client = TestClient(app)
    response = client.post(
        "/generate/propose", json={"topic_id": "mindset-self-doubt", "format": "carousel"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["angle"] == "a proposed angle"
    assert body["mood"] == "bold"
    assert body["reason"] == "because it's punchy"
    assert body["visual_subject"] == "a torn-up to-do list on a kitchen counter"
    assert body["fingerprint"]


def test_propose_route_unknown_topic_returns_404(monkeypatch):
    monkeypatch.setattr(generate_module, "LLMProvider", lambda: _QueueLLM([]))

    client = TestClient(app)
    response = client.post("/generate/propose", json={"topic_id": "does-not-exist", "format": "carousel"})

    assert response.status_code == 404


def test_generate_route_honors_preselected_angle_skips_resampling(monkeypatch):
    # only ONE response queued: if the route re-sampled the angle instead of honoring
    # the preselected one, this would raise IndexError on a second LLM call
    monkeypatch.setattr(generate_module, "LLMProvider", lambda: _QueueLLM([_DRAFT_CAROUSEL_JSON]))
    monkeypatch.setattr(generate_module, "ImageProvider", _FakeImage)

    client = TestClient(app)
    response = client.post(
        "/generate",
        json={
            "topic_id": "mindset-self-doubt",
            "format": "carousel",
            **_NON_TEACHING_PRESELECTED,
            "mood": "celebratory",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["brief"]["angle"] == "her exact accepted angle"
    assert body["brief"]["mood"] == "celebratory"
    assert body["brief"]["approach"] == "question_reflection"


def test_generate_from_brief_route_handles_non_taxonomy_topic_id(monkeypatch):
    """Paste-link briefs have a synthetic topic_id ('paste-link:<hash>') that isn't in
    the taxonomy — /generate/from-brief must run generation without a topic lookup."""
    monkeypatch.setattr(generate_module, "LLMProvider", lambda: _QueueLLM([_DRAFT_CAROUSEL_JSON]))
    monkeypatch.setattr(generate_module, "ImageProvider", _FakeImage)

    client = TestClient(app)
    brief = {
        "topic_id": "paste-link:abc123",
        "topic_name": "A New Law Affecting Women",
        "angle": "reporting on: A New Law Affecting Women",
        "approach": "stat_research",
        "goal": "inform",
        "mood": "wisdom",
        "format": "carousel",
        "slide_count": 4,  # cover, body, closing, conversation (logbook #39 round 7)
        "tone": ["warm"],
        "brand_voice_samples": ["a"],
        "signature_cta": None,
        "requires_citation": True,
        "sensitivity": "normal",
        "sources": [
            {
                "title": "A New Law Affecting Women",
                "author": None,
                "url": "https://example.com/article",
                "excerpt": "excerpt",
                "retrieved_at": "2026-01-01T00:00:00Z",
            }
        ],
        "hero_image_prompt": "a prompt",
        "max_words_per_slide": 30,
    }
    response = client.post(
        "/generate/from-brief",
        json={"brief": brief, "masthead": "WGS — SOCIETY NO. 01", "category": "Society"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["masthead"] == "WGS — SOCIETY NO. 01"
    assert body["brief"]["topic_id"] == "paste-link:abc123"
    assert len(body["post"]["slides"]) == 4
    assert body["post"]["slides"][3]["template_id"] == "carousel_conversation"


def test_reshuffle_image_route_rejects_single_image_format(monkeypatch):
    monkeypatch.setattr(generate_module, "LLMProvider", lambda: _QueueLLM([]))
    monkeypatch.setattr(generate_module, "ImageProvider", _FakeImage)

    client = TestClient(app)
    brief = {
        "topic_id": "mindset-self-doubt",
        "topic_name": "Self-Doubt",
        "angle": "a",
        "approach": "story",
        "goal": "educate",
        "mood": "wisdom",
        "format": "single_image",
        "slide_count": 1,
        "tone": ["warm"],
        "brand_voice_samples": ["a"],
        "signature_cta": None,
        "requires_citation": False,
        "sensitivity": "normal",
        "sources": [],
        "hero_image_prompt": "a prompt",
        "max_words_per_slide": 30,
    }
    response = client.post("/generate/reshuffle-image", json={"brief": brief, "variant": 1})

    assert response.status_code == 400
