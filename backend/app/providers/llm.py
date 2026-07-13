"""Tiered Anthropic adapter — callers ask for a tier ('cheap' | 'strong'), never a model
name directly, so model choice stays a config-level decision (Section 1 / Section 7)."""

from __future__ import annotations

import anthropic

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
    """Wraps Anthropic. Callers pass tier='cheap'|'strong'."""

    def __init__(self, client: anthropic.Anthropic | None = None):
        settings = get_settings()
        self._client = client or anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._models = {"cheap": settings.llm_model_cheap, "strong": settings.llm_model_strong}
        self._cache_enabled = settings.enable_prompt_cache

    def complete(
        self, *, tier: str, system: str, prompt: str, max_tokens: int, cache: bool = True
    ) -> str:
        if tier not in self._models:
            raise ValueError(f"Unknown tier: {tier!r} (expected 'cheap' or 'strong')")

        system_block: dict = {"type": "text", "text": system}
        if cache and self._cache_enabled:
            system_block["cache_control"] = {"type": "ephemeral"}

        response = self._client.messages.create(
            model=self._models[tier],
            system=[system_block],
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
        )
        return "".join(
            block.text for block in response.content if block.type == "text"
        )
