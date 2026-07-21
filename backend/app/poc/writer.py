"""Shared call logic for the POC writer — used by both scripts/poc_writer.py and
routes/poc.py so the two never drift apart. Deliberately minimal: one Sonnet call,
no Haiku, no angle/approach/entry-point sampling, no critique/refine loop. Does not
import from, and is not imported by, anything in the existing generation pipeline
(engine/generator.py, engine/angle_engine.py, routes/generate.py)."""

from __future__ import annotations

from app.poc.prompt import build_poc_system_prompt
from app.poc.prompt_gpt_variant import build_gpt_variant_system_prompt
from app.providers.llm import LLMProvider, strip_json_fence

# variant name -> prompt builder. "current" is the default for every existing
# caller (script with no --variant flag, route with no variant field) — adding
# "gpt" here does not change behavior for anyone who doesn't ask for it.
_PROMPT_BUILDERS = {
    "current": build_poc_system_prompt,
    "gpt": build_gpt_variant_system_prompt,
}

# Generous relative to the existing pipeline's draft_post budget (1500 for a fixed
# ~30-word-per-slide carousel) — these slides are unconstrained flowing paragraphs,
# plus a full second-telling caption, and running out of room mid-JSON is worse than
# a few hundred idle tokens.
POC_MAX_TOKENS = 3000

# A minimal, fixed user turn. The Anthropic API requires a non-empty user message;
# the entire brief — persona, rules, examples, the JSON contract, and the topic
# itself — already lives in the system prompt, verbatim as handed over.
_USER_TURN = "Write the piece now. Output only the JSON object described above, nothing else."


def run_poc_writer(
    topic: str,
    llm: LLMProvider | None = None,
    recent_anchors: list[str] | None = None,
    variant: str = "current",
) -> str:
    """Makes the one Sonnet call and returns the raw JSON text (fence-stripped,
    not yet parsed) — what "the raw JSON result" means for both callers.

    `variant` selects which system prompt to use — "current" (app/poc/prompt.py,
    the default, unchanged behavior for every existing caller) or "gpt"
    (app/poc/prompt_gpt_variant.py, GPT's editorial-workflow architecture, for
    A/B comparison only). `recent_anchors` is a test-harness knob only (see
    FINDINGS.md #1) — an in-memory list passed manually per test batch, not a
    persisted/production mechanism. Appended to the user turn (not the verbatim
    system prompt) so the fixed system prompt text stays byte-for-byte as
    handed over."""
    if variant not in _PROMPT_BUILDERS:
        raise ValueError(f"Unknown variant: {variant!r} (expected 'current' or 'gpt')")
    llm = llm or LLMProvider()
    system = _PROMPT_BUILDERS[variant](topic)
    user_turn = _USER_TURN
    if recent_anchors:
        user_turn += (
            f"\n\nDo not use any of these anchors, they've been used recently: "
            f"{', '.join(recent_anchors)}."
        )
    raw = llm.complete(tier="strong", system=system, prompt=user_turn, max_tokens=POC_MAX_TOKENS)
    return strip_json_fence(raw)
