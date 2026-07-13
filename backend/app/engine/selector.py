"""Daily-pick selector (blueprint Section 10): 3 curated picks, date-seeded so they
don't reshuffle mid-day, weighted by coverage (topics unused recently win) and a soft
brand-niche fit, enforcing category variety, mixing ~2 evergreen + 1 timely (an
awareness day when one is near, otherwise evergreen). Only a hook + thumbnail concept
is precomputed per pick (cheap tier) — the full carousel generates on tap (Phase 3).
A limited reroll is the pressure-release valve when a pick doesn't land."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from app.engine.angle_engine import generate_angle
from app.models.brand_kit import BrandKit
from app.models.enums import Approach
from app.models.memory import MemoryRecord
from app.models.topic import Topic
from app.providers.llm import LLMProvider, strip_json_fence
from app.sources.awareness_calendar import AwarenessDay, upcoming_awareness_days

PICKS_PATH = Path(__file__).resolve().parent.parent.parent / ".cache" / "picks.json"
MAX_REROLLS_PER_DAY = 2


class RerollError(Exception):
    """Raised when a reroll is requested but the daily limit is already used up,
    or no picks have been computed yet for the given date."""


class DailyPick(BaseModel):
    topic_id: str
    topic_name: str
    category: str
    source_type: Literal["evergreen", "timely"]
    approach: Approach
    mood: str
    angle: str
    hook: str
    thumbnail_concept: str
    awareness_day_name: str | None = None


class DailyPicksResult(BaseModel):
    date: date
    picks: list[DailyPick]
    rerolls_used: int = 0


@dataclass
class TopicPick:
    topic: Topic
    source_type: Literal["evergreen", "timely"]
    awareness_day: AwarenessDay | None = None


class PicksStore:
    def __init__(self, path: Path = PICKS_PATH):
        self._path = path

    def _load_all(self) -> dict[str, dict]:
        if not self._path.exists():
            return {}
        return json.loads(self._path.read_text(encoding="utf-8"))

    def _save_all(self, data: dict[str, dict]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def get(self, day: date) -> DailyPicksResult | None:
        raw = self._load_all().get(day.isoformat())
        return DailyPicksResult.model_validate(raw) if raw else None

    def save(self, result: DailyPicksResult) -> None:
        data = self._load_all()
        data[result.date.isoformat()] = json.loads(result.model_dump_json())
        self._save_all(data)


def _topic_weight(topic: Topic, memory: list[MemoryRecord], brand_kit: BrandKit) -> float:
    uses = sum(1 for r in memory if r.topic_id == topic.id)
    coverage_weight = 1.0 / (1 + uses)  # topics unused recently weigh more (coverage)
    niche_bonus = 0.25 if set(topic.tone_defaults) & set(brand_kit.default_tone) else 0.0
    return coverage_weight + niche_bonus


def _weighted_pick_without_category_repeat(
    pool: list[Topic],
    count: int,
    rng: random.Random,
    used_categories: set[str],
    used_topic_ids: set[str],
    weight_fn,
) -> list[Topic]:
    remaining = [t for t in pool if t.id not in used_topic_ids]
    chosen: list[Topic] = []
    for _ in range(count):
        available = [t for t in remaining if t.primary_category not in used_categories] or remaining
        if not available:
            break
        weights = [weight_fn(t) for t in available]
        pick = rng.choices(available, weights=weights, k=1)[0]
        chosen.append(pick)
        used_categories.add(pick.primary_category)
        used_topic_ids.add(pick.id)
        remaining = [t for t in remaining if t.id != pick.id]
    return chosen


def select_daily_picks(
    topics: list[Topic],
    memory: list[MemoryRecord],
    brand_kit: BrandKit,
    target_date: date,
    *,
    awareness_days: list[AwarenessDay] | None = None,
    evergreen_count: int = 2,
    timely_count: int = 1,
    rng: random.Random | None = None,
) -> list[TopicPick]:
    """Enforces category variety (never repeats a primary_category across the 3
    picks) and mixes ~2 evergreen + 1 timely — an awareness day within range fills
    the timely slot when one exists, otherwise it's backfilled with evergreen."""
    rng = rng or random.Random(target_date.isoformat())
    topics_by_id = {t.id: t for t in topics}

    used_categories: set[str] = set()
    used_topic_ids: set[str] = set()
    picks: list[TopicPick] = []

    timely_filled = 0
    for day in upcoming_awareness_days(target_date, awareness_days=awareness_days):
        if timely_filled >= timely_count:
            break
        topic = topics_by_id.get(day.related_topic_id)
        if topic is None or topic.id in used_topic_ids:
            continue
        picks.append(TopicPick(topic=topic, source_type="timely", awareness_day=day))
        used_categories.add(topic.primary_category)
        used_topic_ids.add(topic.id)
        timely_filled += 1

    evergreen_needed = evergreen_count + (timely_count - timely_filled)
    evergreen_topics = _weighted_pick_without_category_repeat(
        topics,
        evergreen_needed,
        rng,
        used_categories,
        used_topic_ids,
        weight_fn=lambda t: _topic_weight(t, memory, brand_kit),
    )
    picks.extend(TopicPick(topic=t, source_type="evergreen") for t in evergreen_topics)

    return picks


def _generate_pitch(
    topic: Topic, angle: str, approach: Approach, mood: str, llm: LLMProvider
) -> tuple[str, str]:
    """One cheap-tier call bundling the picks-screen hook and the cover's thumbnail
    concept into a single JSON response — same cost-saving pattern as angle+mood."""
    system = (
        "You write a short, scroll-stopping hook and a brief visual thumbnail "
        "concept for an Instagram post's picks screen, given its topic, angle, "
        "approach and mood. The hook is a headline, not a full sentence of copy. "
        "The thumbnail concept is a short visual direction (not literal copy).\n"
        'Respond with ONLY JSON, no markdown fence: '
        '{"hook": "...", "thumbnail_concept": "..."}'
    )
    prompt = f"Topic: {topic.name}\nAngle: {angle}\nApproach: {approach.value}\nMood: {mood}"
    raw = llm.complete(tier="cheap", system=system, prompt=prompt, max_tokens=150)

    hook, thumbnail = "", ""
    try:
        data = json.loads(strip_json_fence(raw))
        hook = str(data.get("hook") or "").strip()
        thumbnail = str(data.get("thumbnail_concept") or "").strip()
    except (json.JSONDecodeError, AttributeError):
        pass

    if not hook:
        hook = angle
    if not thumbnail:
        thumbnail = "abstract editorial texture, brand duotone"
    return hook, thumbnail


def build_daily_pick(
    pick: TopicPick,
    memory: list[MemoryRecord],
    llm: LLMProvider,
    *,
    rng: random.Random | None = None,
) -> DailyPick:
    sampled = generate_angle(pick.topic, memory, llm, rng=rng)
    hook, thumbnail = _generate_pitch(pick.topic, sampled.angle, sampled.approach, sampled.mood, llm)
    return DailyPick(
        topic_id=pick.topic.id,
        topic_name=pick.topic.name,
        category=pick.topic.primary_category,
        source_type=pick.source_type,
        approach=sampled.approach,
        mood=sampled.mood,
        angle=sampled.angle,
        hook=hook,
        thumbnail_concept=thumbnail,
        awareness_day_name=pick.awareness_day.name if pick.awareness_day else None,
    )


def run_nightly_picks_job(
    topics: list[Topic],
    memory: list[MemoryRecord],
    brand_kit: BrandKit,
    llm: LLMProvider,
    store: PicksStore,
    target_date: date,
) -> DailyPicksResult:
    """Precompute today's 3 picks (hook + thumbnail only) and persist them, so reads
    for the rest of the day are cache hits, not new LLM calls. Callable directly as a
    batch job (e.g. from a nightly cron) or lazily on first request of the day."""
    rng = random.Random(target_date.isoformat())
    topic_picks = select_daily_picks(topics, memory, brand_kit, target_date, rng=rng)
    daily_picks = [build_daily_pick(p, memory, llm, rng=rng) for p in topic_picks]
    result = DailyPicksResult(date=target_date, picks=daily_picks)
    store.save(result)
    return result


def get_or_compute_daily_picks(
    topics: list[Topic],
    memory: list[MemoryRecord],
    brand_kit: BrandKit,
    llm: LLMProvider,
    store: PicksStore,
    target_date: date,
) -> DailyPicksResult:
    cached = store.get(target_date)
    if cached is not None:
        return cached
    return run_nightly_picks_job(topics, memory, brand_kit, llm, store, target_date)


def reroll_pick(
    topics: list[Topic],
    memory: list[MemoryRecord],
    brand_kit: BrandKit,
    llm: LLMProvider,
    store: PicksStore,
    target_date: date,
    pick_index: int,
) -> DailyPicksResult:
    result = store.get(target_date)
    if result is None:
        raise RerollError(f"no picks computed yet for {target_date.isoformat()}")
    if result.rerolls_used >= MAX_REROLLS_PER_DAY:
        raise RerollError(f"reroll limit ({MAX_REROLLS_PER_DAY}) reached for today")
    if not (0 <= pick_index < len(result.picks)):
        raise IndexError(f"pick_index {pick_index} out of range for {len(result.picks)} picks")

    old_pick = result.picks[pick_index]
    used_topic_ids = {p.topic_id for p in result.picks}
    used_categories = {p.category for i, p in enumerate(result.picks) if i != pick_index}

    rng = random.Random(f"{target_date.isoformat()}:reroll:{result.rerolls_used}")
    topics_by_id = {t.id: t for t in topics}
    pool = [t for t in topics if t.id not in used_topic_ids and t.primary_category not in used_categories]
    pool = pool or [t for t in topics if t.id not in used_topic_ids] or list(topics_by_id.values())
    weights = [_topic_weight(t, memory, brand_kit) for t in pool]
    new_topic = rng.choices(pool, weights=weights, k=1)[0]

    new_pick = build_daily_pick(
        TopicPick(topic=new_topic, source_type=old_pick.source_type), memory, llm, rng=rng
    )
    result.picks[pick_index] = new_pick
    result.rerolls_used += 1
    store.save(result)
    return result
