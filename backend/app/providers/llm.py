"""Tiered LLM adapter -- callers ask for a tier ('cheap' | 'strong'), never a model
name directly, so model choice stays a config-level decision (Section 1 / Section 7).

Provider defaults to OpenAI (gpt-5.6-luna cheap / gpt-5.5 strong) as of the
locked-decision reversal in docs/logbook.md -- driven by real A/B evidence
(docs/direct-write-poc.md Section 9) plus Anthropic running out of production
credits. The Anthropic/Claude path remains fully functional, unchanged, and
callable explicitly -- either per-call (`LLMProvider(provider="anthropic")`)
or fleet-wide via the LLM_PROVIDER env var, no redeploy needed -- the same
explicit-opt-in pattern the POC used when gpt-5.5 became its own default
(direct-write-poc.md Section 9)."""

from __future__ import annotations

import anthropic
import openai

from app.config import get_settings


def strip_json_fence(text: str) -> str:
    """LLMs sometimes wrap JSON in a ```json ... ``` fence despite instructions not to."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


class LLMProvider:
    """Wraps either OpenAI or Anthropic behind one tier-based interface. Provider is
    resolved once at construction (never per-call), so a single instance never mixes
    providers mid-request -- callers that want Anthropic explicitly pass
    provider="anthropic"; everyone else gets the OpenAI default."""

    def __init__(self, *, provider: str | None = None, client: object | None = None):
        settings = get_settings()
        self._provider = provider or settings.llm_provider
        if self._provider not in ("openai", "anthropic"):
            raise ValueError(f"Unknown provider: {self._provider!r} (expected 'openai' or 'anthropic')")

        if self._provider == "openai":
            self._client = client or openai.OpenAI(api_key=settings.openai_api_key)
            self._models = {"cheap": settings.llm_model_cheap, "strong": settings.llm_model_strong}
        else:
            self._client = client or anthropic.Anthropic(api_key=settings.anthropic_api_key)
            self._models = {
                "cheap": settings.llm_model_cheap_anthropic,
                "strong": settings.llm_model_strong_anthropic,
            }
        self._cache_enabled = settings.enable_prompt_cache

    def complete(
        self, *, tier: str, system: str, prompt: str, max_tokens: int, cache: bool = True
    ) -> str:
        if tier not in self._models:
            raise ValueError(f"Unknown tier: {tier!r} (expected 'cheap' or 'strong')")

        if self._provider == "openai":
            return self._complete_openai(tier=tier, system=system, prompt=prompt, max_tokens=max_tokens)
        return self._complete_anthropic(
            tier=tier, system=system, prompt=prompt, max_tokens=max_tokens, cache=cache
        )

    def _complete_openai(self, *, tier: str, system: str, prompt: str, max_tokens: int) -> str:
        # gpt-5.5/gpt-5.6-luna spend part of max_completion_tokens on invisible
        # reasoning tokens before ever emitting visible content -- the OpenAI-side
        # equivalent of this file's existing thinking={"type": "disabled"} fix for
        # Sonnet 5's extended thinking, same failure class. Confirmed live at cheap-
        # tier budgets (100-300): the entire budget was consumed by reasoning and
        # content came back empty with the default reasoning_effort. Initially left
        # unset for the strong tier on the assumption that its wider budgets
        # (400-1500) had enough headroom -- disproven live: critique_post's real
        # single_image budget (500) against a realistic draft-length prompt also
        # returned empty (500/500 tokens spent on reasoning, 0 on content).
        # Reasoning-token consumption scales with prompt complexity, not just a
        # fixed overhead, so no fixed budget in this codebase's actual range is
        # provably safe left at the default. reasoning_effort="none" applies to
        # both tiers unconditionally -- confirmed live to eliminate reasoning-token
        # consumption entirely (reasoning_tokens=0) and return full content at
        # every real budget this codebase uses.
        response = self._client.chat.completions.create(
            model=self._models[tier],
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            max_completion_tokens=max_tokens,
            reasoning_effort="none",
        )
        return response.choices[0].message.content or ""

    def _complete_anthropic(
        self, *, tier: str, system: str, prompt: str, max_tokens: int, cache: bool
    ) -> str:
        system_block: dict = {"type": "text", "text": system}
        if cache and self._cache_enabled:
            system_block["cache_control"] = {"type": "ephemeral"}

        response = self._client.messages.create(
            model=self._models[tier],
            system=[system_block],
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            # These calls only ever want the final structured/prose output, never a
            # reasoning trace — and left unset, claude-sonnet-5 defaults extended
            # thinking on with an uncontrolled budget that can consume the entire
            # max_tokens, leaving zero tokens for the actual response.
            thinking={"type": "disabled"},
        )
        return "".join(
            block.text for block in response.content if block.type == "text"
        )
