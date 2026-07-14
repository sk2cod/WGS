from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import ValidationError

from app.models.topic import Topic

TOPICS_YAML_PATH = Path(__file__).parent / "topics.yaml"


def load_topics(path: Path = TOPICS_YAML_PATH) -> list[Topic]:
    """Load and validate topics.yaml against the Topic model. Fails loudly: raises
    ValueError listing every problem found, rather than returning partial data."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not raw:
        raise ValueError(f"{path} is empty or not valid YAML")

    topics: list[Topic] = []
    errors: list[str] = []
    seen_ids: set[str] = set()

    for i, entry in enumerate(raw):
        entry_id = entry.get("id", f"<index {i}>") if isinstance(entry, dict) else f"<index {i}>"
        try:
            topic = Topic.model_validate(entry)
        except ValidationError as exc:
            errors.append(f"topic '{entry_id}': {exc}")
            continue

        if topic.primary_category not in topic.categories:
            errors.append(
                f"topic '{topic.id}': primary_category '{topic.primary_category}' "
                f"is not present in categories {topic.categories}"
            )
        if topic.id in seen_ids:
            errors.append(f"duplicate topic id '{topic.id}'")
        seen_ids.add(topic.id)
        if topic.requires_citation and not topic.knowledge_hints:
            errors.append(
                f"topic '{topic.id}': requires_citation is True but knowledge_hints is "
                "empty — the generator has nothing to ground factual claims against "
                "outside the paste-link flow, which reintroduces the contradictory-prompt "
                "bug (logbook #14). Add at least one knowledge_hints entry."
            )

        topics.append(topic)

    if errors:
        raise ValueError(
            f"Invalid {path.name} ({len(errors)} problem(s)):\n" + "\n".join(f"  - {e}" for e in errors)
        )

    return topics


@lru_cache(maxsize=1)
def get_topics() -> tuple[Topic, ...]:
    """Cached, validated topic list — call at app startup so a bad topics.yaml fails
    loudly before the server accepts traffic."""
    return tuple(load_topics())


def get_topics_by_id() -> dict[str, Topic]:
    return {t.id: t for t in get_topics()}
