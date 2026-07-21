"""Standalone POC script — one Sonnet call, the verbatim system prompt, raw JSON out.

No Haiku, no seed_angle/approach/entry_point sampling, no critique/refine loop —
deliberately isolated from the real pipeline (engine/generator.py, engine/angle_engine.py).

Usage (from backend/):
    uv run python scripts/poc_writer.py "a topic string, e.g. Boundaries"
    uv run python scripts/poc_writer.py "Boundaries" --exclude-anchors "kintsugi,segmented sleep"
    uv run python scripts/poc_writer.py "Boundaries" --variant gpt

--exclude-anchors is a test-harness-only knob (see app/poc/FINDINGS.md #1) — an
in-memory list you pass by hand per batch, not a persisted mechanism.
--variant selects which system prompt to use: "current" (default, app/poc/prompt.py)
or "gpt" (app/poc/prompt_gpt_variant.py, for A/B comparison only).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow `uv run python scripts/poc_writer.py ...` from backend/ without installing
# the package — mirrors how backend/tests already resolve `app`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.poc.writer import run_poc_writer  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Standalone POC writer script.")
    parser.add_argument("topic", nargs="+", help='Topic string, e.g. "Boundaries"')
    parser.add_argument(
        "--exclude-anchors",
        default="",
        help="Comma-separated recently-used anchors to exclude, e.g. 'kintsugi,segmented sleep'",
    )
    parser.add_argument(
        "--variant",
        choices=["current", "gpt"],
        default="current",
        help="Which system prompt to use (default: current)",
    )
    args = parser.parse_args()

    topic = " ".join(args.topic)
    recent_anchors = [a.strip() for a in args.exclude_anchors.split(",") if a.strip()] or None

    raw_json = run_poc_writer(topic, recent_anchors=recent_anchors, variant=args.variant)
    print(raw_json)


if __name__ == "__main__":
    main()
