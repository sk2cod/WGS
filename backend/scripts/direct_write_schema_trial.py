"""One-off real-API trial script for task "#19" (rewriting draft_carousel_direct's
cover/body/closing prompt and schema). Not part of the app -- calls the real,
live LLM provider directly against draft_carousel_direct() for a handful of real
topics, and prints the raw structured output plus word counts, so the actual
generated content can be read and judged, not just the instructions that produced
it. Run from backend/ with the real .env loaded:

    .venv/Scripts/python.exe scripts/direct_write_schema_trial.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, ".")

SCRATCH_DIR = r"C:\Users\saurabh.k\AppData\Local\Temp\claude\C--Users-saurabh-k-PycharmProjects-PythonProject-WGS\b5847c58-0210-472f-9293-f481adbab38f\scratchpad"
os.makedirs(SCRATCH_DIR, exist_ok=True)

from app.engine.angle_engine import assemble_carousel_context
from app.engine.brief_builder import build_brief
from app.engine.generator import draft_carousel_direct
from app.engine.validator import validate_post
from app.models.enums import Approach, Format
from app.providers.llm import LLMProvider
from app.taxonomy.loader import get_topics_by_id
from app.taxonomy.wgs_brand_kit import WGS_BRAND_KIT

TOPIC_IDS = [
    "mindset-perfectionism",
    "career-pay-scale",
]


def main() -> None:
    topics_by_id = get_topics_by_id()
    llm = LLMProvider()

    for topic_id in TOPIC_IDS:
        topic = topics_by_id[topic_id]
        context = assemble_carousel_context(topic, memory=[])
        provisional_brief = build_brief(
            topic_id=topic.id,
            topics_by_id=topics_by_id,
            angle="(pending)",
            approach=Approach.STORY,
            mood="wisdom",
            format=Format.CAROUSEL,
            brand_kit=WGS_BRAND_KIT,
            memory=[],
            goal="educate",
        ).brief

        post, anchor, mood, visual_subject = draft_carousel_direct(
            provisional_brief, WGS_BRAND_KIT, llm, topic, context
        )
        brief = provisional_brief.model_copy(update={"angle": anchor, "mood": mood})
        validation = validate_post(
            brief, WGS_BRAND_KIT, post, [], f"{topic_id}:{anchor}", carousel_writer="direct_write"
        )

        cover = post.slides[0]
        bodies = post.slides[1:4]
        closing = post.slides[4]
        conversation = post.slides[5]

        print("=" * 100)
        print(f"TOPIC: {topic_id}  (requires_citation={topic.requires_citation})")
        print(f"ANCHOR: {anchor}")
        print(f"MOOD: {mood}")
        print(f"VISUAL_SUBJECT: {visual_subject}")
        print("-" * 100)
        print(f"HEADLINE ({len(cover.headline_word.split())} words): {cover.headline_word!r}")
        print(f"COVER_BODY ({len(cover.cover_body.split())} words): {cover.cover_body!r}")
        print(
            f"cover combined words: {len((cover.headline_word + ' ' + cover.cover_body).split())}"
        )
        for i, b in enumerate(bodies, start=1):
            found = b.accent_phrase in b.body if b.accent_phrase else False
            print(
                f"BODY {i} ({len(b.body.split())} words, accent_phrase found={found}): "
                f"body={b.body!r} | accent_phrase={b.accent_phrase!r}"
            )
        sentence_count = closing.takeaway.count(". ") + (1 if closing.takeaway.strip() else 0)
        print(f"CLOSING ({len(closing.takeaway.split())} words, ~{sentence_count} sentences): {closing.takeaway!r}")
        print(f"CONVERSATION QUESTION: {conversation.question!r}")
        print(f"CAPTION: {post.caption!r}")
        print(f"VALIDATION ERRORS: {validation.errors}")
        print()

        out_path = os.path.join(SCRATCH_DIR, f"direct_write_trial_{topic_id}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "topic_id": topic_id,
                    "anchor": anchor,
                    "mood": mood,
                    "slides": [s.model_dump() for s in post.slides],
                    "caption": post.caption,
                },
                f,
                indent=2,
            )


if __name__ == "__main__":
    main()
