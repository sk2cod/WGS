"""Isolated OpenAI backend for the POC writer — a second, optional model provider
alongside the existing Anthropic path (writer.py's default, untouched by this file).

Reads ONLY the OPENAI_API_KEY_POC environment variable, via a self-contained
settings loader defined in this file — deliberately not added to app/config.py's
shared Settings class, so this stays fully isolated from OPENAI_API_KEY (the
existing key used by providers/image.py for hero-image generation). Nothing else
in the codebase reads OPENAI_API_KEY_POC, and this module never reads
OPENAI_API_KEY. Confirmed by grep at build time (see docs/direct-write-poc.md if
this file's history needs re-checking).

Reuses the exact same prompt content as the Anthropic path (build_poc_system_prompt
from app.poc.prompt, or build_gpt_variant_system_prompt from
app.poc.prompt_gpt_variant when variant="gpt") — no prompt text is duplicated or
modified here. Only reached when a caller explicitly asks for provider="openai";
default behavior everywhere else (writer.py, the script, the route) is completely
unchanged."""

from __future__ import annotations

from functools import lru_cache

from openai import OpenAI
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.poc.prompt import build_poc_system_prompt
from app.poc.prompt_gpt_variant import build_gpt_variant_system_prompt
from app.providers.llm import strip_json_fence

# The one and only model this path is allowed to use — never auto-selected,
# never falls back to a different model.
POC_OPENAI_MODEL = "gpt-5.5"

_PROMPT_BUILDERS = {
    "current": build_poc_system_prompt,
    "gpt": build_gpt_variant_system_prompt,
}

_USER_TURN = "Write the piece now. Output only the JSON object described above, nothing else."

# Strict JSON Schema structured output — the same four fields the Anthropic path's
# prompt already asks for in prose; this makes the shape a hard API guarantee
# rather than something inferred from parsing a plain-text JSON response.
#
# Property order here is not cosmetic: OpenAI's structured-output mode generates
# fields in the order they're declared in `properties`, so this is what actually
# enforces "write caption before slides" on this path — the prose instruction in
# prompt.py alone would only be a suggestion for a model that isn't schema-bound
# the way gpt-5.5 is here. Keep this in sync with prompt.py's own field order if
# either ever changes.
POC_RESPONSE_JSON_SCHEMA = {
    "name": "poc_carousel_piece",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "anchor": {"type": "string"},
            "caption": {"type": "string"},
            "slides": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 4,
                "maxItems": 7,
            },
            "conversation_question": {"type": "string"},
        },
        "required": ["anchor", "caption", "slides", "conversation_question"],
        "additionalProperties": False,
    },
}


class _PocOpenAISettings(BaseSettings):
    """Self-contained, isolated settings loader — reads only OPENAI_API_KEY_POC
    from .env. Not app.config.Settings; adding a field there would put this key
    in the same shared settings object as OPENAI_API_KEY, which is exactly the
    cross-contamination this module is built to avoid."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    openai_api_key_poc: str = ""


@lru_cache(maxsize=1)
def _get_poc_openai_settings() -> _PocOpenAISettings:
    return _PocOpenAISettings()


def _build_client() -> OpenAI:
    settings = _get_poc_openai_settings()
    if not settings.openai_api_key_poc:
        raise RuntimeError(
            "OPENAI_API_KEY_POC is not set (checked backend/.env). This POC OpenAI "
            "path deliberately does not fall back to OPENAI_API_KEY — add "
            "OPENAI_API_KEY_POC explicitly before using provider='openai'."
        )
    # api_key passed explicitly — never relies on the SDK's own OPENAI_API_KEY
    # env var fallback, which would silently pick up the wrong (shared) key.
    return OpenAI(api_key=settings.openai_api_key_poc)


def check_model_accessible(client: OpenAI | None = None) -> str:
    """Cheapest possible confirmation that POC_OPENAI_MODEL is reachable with this
    key: a model-retrieve call, no generation tokens spent. Raises on failure.
    Returns the model id as confirmed by the API."""
    client = client or _build_client()
    model = client.models.retrieve(POC_OPENAI_MODEL)
    return model.id


def run_poc_writer_openai(
    topic: str,
    client: OpenAI | None = None,
    recent_anchors: list[str] | None = None,
    variant: str = "current",
) -> str:
    """OpenAI equivalent of writer.py's run_poc_writer() for the Anthropic path —
    same inputs, same return shape (raw JSON text). Uses the exact same system
    prompt content as the Anthropic path (see _PROMPT_BUILDERS above)."""
    if variant not in _PROMPT_BUILDERS:
        raise ValueError(f"Unknown variant: {variant!r} (expected 'current' or 'gpt')")

    client = client or _build_client()
    system = _PROMPT_BUILDERS[variant](topic)
    user_turn = _USER_TURN
    if recent_anchors:
        user_turn += (
            f"\n\nDo not use any of these anchors, they've been used recently: "
            f"{', '.join(recent_anchors)}."
        )

    response = client.chat.completions.create(
        model=POC_OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_turn},
        ],
        response_format={"type": "json_schema", "json_schema": POC_RESPONSE_JSON_SCHEMA},
    )
    raw = response.choices[0].message.content or ""
    return strip_json_fence(raw)
