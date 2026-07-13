"""Awareness-days calendar — the one pre-loaded automated timely source (blueprint
Section 10): predictable a year out, free content anchors. Each day links to an
existing authored Topic so it flows through the same pipeline as an evergreen pick,
just tagged source_type="timely" with the day's framing carried in `note`."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class AwarenessDay(BaseModel):
    id: str
    name: str
    month: int
    day: int
    related_topic_id: str
    note: str            # short framing injected into the angle prompt


AWARENESS_DAYS: list[AwarenessDay] = [
    AwarenessDay(
        id="galentines-day",
        name="Galentine's Day",
        month=2,
        day=13,
        related_topic_id="relationships-friendship-boundaries",
        note="a day about celebrating women's friendships",
    ),
    AwarenessDay(
        id="international-womens-day",
        name="International Women's Day",
        month=3,
        day=8,
        related_topic_id="inspiring-women-who-changed-history",
        note="the global day honoring women's achievements",
    ),
    AwarenessDay(
        id="equal-pay-day",
        name="Equal Pay Day",
        month=3,
        day=12,
        related_topic_id="society-gender-pay-gap",
        note="marks how far into the year women must work to earn what men earned last year",
    ),
    AwarenessDay(
        id="world-health-day",
        name="World Health Day",
        month=4,
        day=7,
        related_topic_id="health-reproductive-literacy",
        note="the WHO's annual global health awareness day",
    ),
    AwarenessDay(
        id="menstrual-hygiene-day",
        name="Menstrual Hygiene Day",
        month=5,
        day=28,
        related_topic_id="health-hormonal-cycle-basics",
        note="a day for open, myth-free conversation about menstrual health",
    ),
    AwarenessDay(
        id="international-self-care-day",
        name="International Self-Care Day",
        month=7,
        day=24,
        related_topic_id="wellness-rest-is-not-lazy",
        note="a day reframing rest and self-care as maintenance, not indulgence",
    ),
    AwarenessDay(
        id="world-mental-health-day",
        name="World Mental Health Day",
        month=10,
        day=10,
        related_topic_id="wellness-stress-regulation",
        note="the global day for mental health awareness",
    ),
    AwarenessDay(
        id="international-day-of-the-girl",
        name="International Day of the Girl",
        month=10,
        day=11,
        related_topic_id="career-imposter-syndrome",
        note="a day centering girls' and women's confidence and potential",
    ),
]


def _nearest_occurrence(month: int, day: int, target: date) -> date:
    """The occurrence of `month`/`day` (this year, last year, or next year) closest
    in absolute distance to `target` — handles the wraparound at year boundaries."""
    candidates = [date(target.year + offset, month, day) for offset in (-1, 0, 1)]
    return min(candidates, key=lambda d: abs((d - target).days))


def upcoming_awareness_days(
    target_date: date,
    *,
    awareness_days: list[AwarenessDay] | None = None,
    window_days: int = 14,
) -> list[AwarenessDay]:
    """Awareness days whose nearest occurrence falls within `window_days` of
    `target_date` (either direction), nearest first."""
    days = AWARENESS_DAYS if awareness_days is None else awareness_days
    scored = [
        (day, abs((_nearest_occurrence(day.month, day.day, target_date) - target_date).days))
        for day in days
    ]
    in_window = [(day, delta) for day, delta in scored if delta <= window_days]
    in_window.sort(key=lambda pair: pair[1])
    return [day for day, _delta in in_window]
