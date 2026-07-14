import pytest

from app.models.enums import Sensitivity
from app.taxonomy.approaches import APPROACHES
from app.taxonomy.entry_points import ENTRY_POINTS
from app.taxonomy.loader import get_topics, get_topics_by_id, load_topics
from app.taxonomy.voice_register import APPROACH_REGISTER

EXPECTED_CATEGORIES = {
    "Mindset",
    "Career",
    "Wellness",
    "Women's Health",
    "Relationships",
    "Society",
    "Inspiring Women",
}


def test_approaches_and_entry_points_derive_from_enums():
    assert APPROACHES == [
        "educational", "myth_vs_fact", "checklist", "story",
        "stat_research", "question_reflection", "framework", "common_mistakes",
    ]
    assert ENTRY_POINTS == [
        "a_mistake", "a_question", "a_contrarian_take", "a_stat", "a_relatable_moment",
    ]
    assert set(APPROACH_REGISTER) == set(APPROACHES)
    assert set(APPROACH_REGISTER.values()) == {"poetic", "direct"}


def test_topics_yaml_loads_and_validates():
    topics = load_topics()
    assert 15 <= len(topics) <= 20

    ids = [t.id for t in topics]
    assert len(ids) == len(set(ids)), "topic ids must be unique"

    seen_categories = set()
    for topic in topics:
        assert topic.primary_category in topic.categories
        assert 3 <= len(topic.seed_angles) <= 5
        assert len(topic.suitable_formats) >= 1
        seen_categories.update(topic.categories)
        if topic.sensitivity == Sensitivity.HEALTH:
            assert topic.requires_citation is True

    assert EXPECTED_CATEGORIES.issubset(seen_categories)


def test_get_topics_is_cached_and_indexable():
    topics = get_topics()
    assert topics is get_topics()  # lru_cache singleton

    by_id = get_topics_by_id()
    assert len(by_id) == len(topics)
    for topic in topics:
        assert by_id[topic.id] is topic


def test_load_topics_rejects_mismatched_primary_category(tmp_path):
    bad_yaml = tmp_path / "bad_topics.yaml"
    bad_yaml.write_text(
        """
- id: broken
  name: Broken Topic
  categories: ["Mindset"]
  primary_category: "Career"
  tone_defaults: ["warm"]
  suitable_formats: ["carousel"]
  seed_angles: ["a", "b", "c"]
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="not present in categories"):
        load_topics(bad_yaml)


def test_load_topics_rejects_citation_required_without_knowledge_hints(tmp_path):
    """Logbook #14: requires_citation with no knowledge_hints and no pinned Source
    objects is a contradictory prompt (nothing to ground factual claims against) —
    the loader must fail loudly rather than let this recur as topics.yaml grows."""
    bad_yaml = tmp_path / "bad_topics.yaml"
    bad_yaml.write_text(
        """
- id: broken
  name: Broken Topic
  categories: ["Mindset"]
  primary_category: "Mindset"
  tone_defaults: ["warm"]
  suitable_formats: ["carousel"]
  seed_angles: ["a", "b", "c"]
  requires_citation: true
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="knowledge_hints is empty"):
        load_topics(bad_yaml)
