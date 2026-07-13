from datetime import date

from app.sources.awareness_calendar import (
    AWARENESS_DAYS,
    _nearest_occurrence,
    upcoming_awareness_days,
)
from app.taxonomy.loader import get_topics_by_id


def test_nearest_occurrence_handles_year_wraparound():
    nearest = _nearest_occurrence(1, 2, date(2026, 12, 30))
    assert nearest == date(2027, 1, 2)


def test_nearest_occurrence_same_year():
    nearest = _nearest_occurrence(3, 8, date(2026, 3, 1))
    assert nearest == date(2026, 3, 8)


def test_upcoming_awareness_days_includes_days_within_window():
    upcoming = upcoming_awareness_days(date(2026, 3, 1), window_days=14)
    names = {d.name for d in upcoming}
    assert "International Women's Day" in names
    assert "Equal Pay Day" in names


def test_upcoming_awareness_days_excludes_days_outside_window():
    upcoming = upcoming_awareness_days(date(2026, 3, 1), window_days=14)
    names = {d.name for d in upcoming}
    assert "Galentine's Day" not in names  # 16 days away, outside a 14-day window


def test_upcoming_awareness_days_sorted_nearest_first():
    target = date(2026, 3, 1)
    upcoming = upcoming_awareness_days(target, window_days=14)
    deltas = [
        abs((_nearest_occurrence(d.month, d.day, target) - target).days) for d in upcoming
    ]
    assert deltas == sorted(deltas)


def test_upcoming_awareness_days_empty_when_far_from_any_day():
    upcoming = upcoming_awareness_days(date(2026, 6, 20), window_days=5)
    assert upcoming == []


def test_all_related_topic_ids_exist_in_taxonomy():
    topics_by_id = get_topics_by_id()
    for day in AWARENESS_DAYS:
        assert day.related_topic_id in topics_by_id, day.related_topic_id
