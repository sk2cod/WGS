import json
import random
from datetime import date

import pytest

from app.engine.selector import (
    MAX_REROLLS_PER_DAY,
    PicksStore,
    RerollError,
    TopicPick,
    _topic_weight,
    build_daily_pick,
    get_or_compute_daily_picks,
    reroll_pick,
    run_nightly_picks_job,
    select_daily_picks,
)
from app.models.enums import Approach
from app.models.memory import MemoryRecord
from app.sources.awareness_calendar import AwarenessDay
from app.taxonomy.loader import get_topics, get_topics_by_id
from app.taxonomy.wgs_brand_kit import WGS_BRAND_KIT

ANGLE_JSON = json.dumps({"angle": "a specific angle", "mood": "wisdom"})
PITCH_JSON = json.dumps({"hook": "a hook", "thumbnail_concept": "a concept"})

# no real awareness day falls within 14 days of this date (checked against AWARENESS_DAYS)
NO_AWARENESS_DATE = date(2026, 6, 20)


class _QueueLLM:
    def __init__(self, responses):
        self._responses = list(responses)

    def complete(self, *, tier, system, prompt, max_tokens, cache=True):
        return self._responses.pop(0)


class _ExplodingLLM:
    def complete(self, **kwargs):
        raise AssertionError("should not call the LLM on a cache hit")


def test_select_daily_picks_enforces_category_variety():
    picks = select_daily_picks(
        list(get_topics()),
        memory=[],
        brand_kit=WGS_BRAND_KIT,
        target_date=NO_AWARENESS_DATE,
        awareness_days=[],
        rng=random.Random(0),
    )
    categories = [p.topic.primary_category for p in picks]
    assert len(categories) == len(set(categories))
    assert len(picks) == 3
    assert all(p.source_type == "evergreen" for p in picks)


def test_select_daily_picks_uses_timely_slot_when_awareness_day_near():
    custom_day = AwarenessDay(
        id="test-day",
        name="Test Day",
        month=6,
        day=20,
        related_topic_id="inspiring-women-who-changed-history",
        note="test",
    )
    picks = select_daily_picks(
        list(get_topics()),
        memory=[],
        brand_kit=WGS_BRAND_KIT,
        target_date=NO_AWARENESS_DATE,
        awareness_days=[custom_day],
        rng=random.Random(0),
    )
    timely = [p for p in picks if p.source_type == "timely"]
    assert len(timely) == 1
    assert timely[0].topic.id == "inspiring-women-who-changed-history"
    assert len(picks) == 3


def test_select_daily_picks_is_deterministic_for_same_seed():
    topics = list(get_topics())
    first = select_daily_picks(
        topics,
        memory=[],
        brand_kit=WGS_BRAND_KIT,
        target_date=NO_AWARENESS_DATE,
        awareness_days=[],
        rng=random.Random(42),
    )
    second = select_daily_picks(
        topics,
        memory=[],
        brand_kit=WGS_BRAND_KIT,
        target_date=NO_AWARENESS_DATE,
        awareness_days=[],
        rng=random.Random(42),
    )
    assert [p.topic.id for p in first] == [p.topic.id for p in second]


def test_topic_weight_boosts_unused_topics_over_recently_used():
    topic = get_topics_by_id()["mindset-self-doubt"]
    memory = [
        MemoryRecord(
            id=f"m{i}",
            date=date(2026, 1, 1),
            topic_id=topic.id,
            category=topic.primary_category,
            angle="a",
            approach=Approach.STORY,
            format="carousel",
            mood="wisdom",
            hook="h",
            fingerprint=f"fp{i}",
            status="exported",
        )
        for i in range(3)
    ]
    unused_weight = _topic_weight(topic, [], WGS_BRAND_KIT)
    used_weight = _topic_weight(topic, memory, WGS_BRAND_KIT)
    assert unused_weight > used_weight


def test_build_daily_pick_composes_angle_and_pitch_in_two_cheap_calls():
    topic = get_topics_by_id()["mindset-self-doubt"]
    llm = _QueueLLM([ANGLE_JSON, PITCH_JSON])
    pick = build_daily_pick(
        TopicPick(topic=topic, source_type="evergreen"), [], llm, rng=random.Random(0)
    )
    assert pick.angle == "a specific angle"
    assert pick.mood == "wisdom"
    assert pick.hook == "a hook"
    assert pick.thumbnail_concept == "a concept"
    assert pick.source_type == "evergreen"
    assert pick.awareness_day_name is None


def test_run_nightly_picks_job_persists_and_cache_is_reused(tmp_path):
    store = PicksStore(path=tmp_path / "picks.json")
    topics = list(get_topics())
    llm = _QueueLLM([ANGLE_JSON, PITCH_JSON] * 3)

    result = run_nightly_picks_job(topics, [], WGS_BRAND_KIT, llm, store, NO_AWARENESS_DATE)
    assert len(result.picks) == 3
    assert store.get(NO_AWARENESS_DATE) is not None

    cached = get_or_compute_daily_picks(
        topics, [], WGS_BRAND_KIT, _ExplodingLLM(), store, NO_AWARENESS_DATE
    )
    assert [p.topic_id for p in cached.picks] == [p.topic_id for p in result.picks]


def test_reroll_pick_swaps_pick_and_increments_counter(tmp_path):
    store = PicksStore(path=tmp_path / "picks.json")
    topics = list(get_topics())
    llm = _QueueLLM([ANGLE_JSON, PITCH_JSON] * 4)

    run_nightly_picks_job(topics, [], WGS_BRAND_KIT, llm, store, NO_AWARENESS_DATE)
    updated = reroll_pick(topics, [], WGS_BRAND_KIT, llm, store, NO_AWARENESS_DATE, pick_index=0)
    assert updated.rerolls_used == 1
    assert store.get(NO_AWARENESS_DATE).rerolls_used == 1


def test_reroll_pick_enforces_daily_limit(tmp_path):
    store = PicksStore(path=tmp_path / "picks.json")
    topics = list(get_topics())
    calls_needed = 3 + MAX_REROLLS_PER_DAY
    llm = _QueueLLM([ANGLE_JSON, PITCH_JSON] * calls_needed)

    run_nightly_picks_job(topics, [], WGS_BRAND_KIT, llm, store, NO_AWARENESS_DATE)
    for _ in range(MAX_REROLLS_PER_DAY):
        reroll_pick(topics, [], WGS_BRAND_KIT, llm, store, NO_AWARENESS_DATE, pick_index=0)

    with pytest.raises(RerollError):
        reroll_pick(topics, [], WGS_BRAND_KIT, llm, store, NO_AWARENESS_DATE, pick_index=0)


def test_reroll_pick_raises_when_no_picks_computed_yet(tmp_path):
    store = PicksStore(path=tmp_path / "picks.json")
    with pytest.raises(RerollError):
        reroll_pick(
            list(get_topics()), [], WGS_BRAND_KIT, _QueueLLM([]), store, NO_AWARENESS_DATE, pick_index=0
        )


def test_reroll_pick_raises_on_invalid_index(tmp_path):
    store = PicksStore(path=tmp_path / "picks.json")
    topics = list(get_topics())
    llm = _QueueLLM([ANGLE_JSON, PITCH_JSON] * 3)
    run_nightly_picks_job(topics, [], WGS_BRAND_KIT, llm, store, NO_AWARENESS_DATE)
    with pytest.raises(IndexError):
        reroll_pick(topics, [], WGS_BRAND_KIT, llm, store, NO_AWARENESS_DATE, pick_index=99)
