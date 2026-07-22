"""Settings, env vars, cost flags — Section 5 / Section 11 of implementation-guide.md."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- AI providers ---
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    # Default provider for LLMProvider (app/providers/llm.py) -- "openai" as of the
    # locked-decision reversal (docs/logbook.md). "anthropic" remains fully
    # functional, selectable per-instance (LLMProvider(provider="anthropic")) or
    # fleet-wide by setting this env var, no redeploy needed.
    llm_provider: str = "openai"
    llm_model_cheap: str = "gpt-5.6-luna"
    llm_model_strong: str = "gpt-5.5"
    # Only read when provider="anthropic" -- unchanged from the original Claude
    # models, kept alive and selectable, not degraded.
    llm_model_cheap_anthropic: str = "claude-haiku-4-5-20251001"
    llm_model_strong_anthropic: str = "claude-sonnet-5"
    image_model: str = "gpt-image-2"

    # --- Supabase ---
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_db_url: str = ""

    # --- Cost / quality flags ---
    image_quality: str = "medium"        # medium | low
    image_size: str = "1024x1536"        # portrait
    enable_critique: bool = True         # draft -> critique -> refine on every post
    enable_prompt_cache: bool = True

    # --- CORS ---
    frontend_origin: str = "http://localhost:3000"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
