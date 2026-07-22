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
    # Carousel writer, routes/generate.py::run_generate (logbook #43-46) --
    # "direct_write" is the single-call port (draft_carousel_direct), default
    # as of #46; "legacy" is the opt-in fallback to the original sample_cell ->
    # generate_angle -> build_brief -> generate_post chain (logbook #39),
    # same escape-hatch pattern as LLM_PROVIDER. single_image is unaffected
    # by this flag either way -- it never reads it.
    #
    # Deliberately never "v1" (logbook #47): docs/direct-write-poc.md locks
    # "v1"/"v2" to mean only the hand-written writing-style reference pieces
    # (Shimenawa, Shmita, mad money, amae) -- never a pipeline or code path.
    # This flag's old chain is "legacy", full stop, to avoid exactly that
    # collision. If you're about to type "v1" to describe a pipeline or code
    # path anywhere in this codebase, stop -- that word is reserved.
    carousel_writer: str = "direct_write"

    # --- CORS ---
    frontend_origin: str = "http://localhost:3000"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
