import json
import random
from datetime import date

from app.engine.angle_engine import DEFAULT_MOOD, generate_angle, sample_cell
from app.models.enums import Approach
from app.models.memory import MemoryRecord
from app.taxonomy.approaches import APPROACHES
from app.taxonomy.loader import get_topics_by_id


class _FakeLLM:
    def __init__(self, response: str):
        self._response = response

    def complete(self, *, tier, system, prompt, max_tokens, cache=True):
        return self._response


def _used_record(topic_id: str, sub: str, approach: str) -> MemoryRecord:
    return MemoryRecord(
        id=f"m-{sub}-{approach}",
        date=date(2026, 1, 1),
        topic_id=topic_id,
        category="Mindset",
        angle="x",
        approach=Approach(approach),
        format="carousel",
        mood="wisdom",
        hook="h",
        fingerprint=f"{topic_id}:{sub}:{approach}",
        status="exported",
    )


def test_sample_cell_excludes_used_fingerprints():
    topic = get_topics_by_id()["mindset-reframing-self-doubt"]
    target_sub = topic.seed_angles[0]

    used = [
        _used_record(topic.id, sub, a)
        for sub in topic.seed_angles
        for a in APPROACHES
        if not (sub == target_sub and a == Approach.STORY.value)
    ]

    sub, approach, _entry = sample_cell(topic, used, rng=random.Random(0))
    assert sub == target_sub
    assert approach == Approach.STORY


def test_sample_cell_falls_back_to_full_pool_when_topic_exhausted():
    topic = get_topics_by_id()["mindset-reframing-self-doubt"]
    used = [_used_record(topic.id, sub, a) for sub in topic.seed_angles for a in APPROACHES]

    # every combo for this topic is "used" — sample_cell must still return something
    sub, approach, entry = sample_cell(topic, used, rng=random.Random(0))
    assert sub in topic.seed_angles
    assert approach.value in APPROACHES


def test_generate_angle_parses_json_and_tags_mood():
    topic = get_topics_by_id()["mindset-reframing-self-doubt"]
    llm = _FakeLLM(json.dumps({"angle": "a very specific angle", "mood": "bold"}))
    result = generate_angle(topic, [], llm, rng=random.Random(1))
    assert result.angle == "a very specific angle"
    assert result.mood == "bold"
    assert result.fingerprint == f"{topic.id}:{result.sub_concept}:{result.approach.value}"


def test_generate_angle_falls_back_to_wisdom_on_invalid_mood():
    topic = get_topics_by_id()["mindset-reframing-self-doubt"]
    llm = _FakeLLM(json.dumps({"angle": "specific angle", "mood": "sad"}))
    result = generate_angle(topic, [], llm, rng=random.Random(2))
    assert result.mood == DEFAULT_MOOD


def test_generate_angle_falls_back_on_malformed_json():
    topic = get_topics_by_id()["mindset-reframing-self-doubt"]
    llm = _FakeLLM("not json at all")
    result = generate_angle(topic, [], llm, rng=random.Random(3))
    assert result.mood == DEFAULT_MOOD
    assert result.angle  # falls back to the sampled sub-concept, never empty


def test_generate_angle_strips_markdown_fence():
    topic = get_topics_by_id()["mindset-reframing-self-doubt"]
    payload = json.dumps({"angle": "fenced angle", "mood": "celebratory"})
    llm = _FakeLLM(f"```json\n{payload}\n```")
    result = generate_angle(topic, [], llm, rng=random.Random(4))
    assert result.angle == "fenced angle"
    assert result.mood == "celebratory"
