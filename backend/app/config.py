"""Settings, env vars, cost flags — Section 5 / Section 11 of implementation-guide.md."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- AI providers ---
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    llm_model_cheap: str = "claude-haiku-4-5-20251001"
    llm_model_strong: str = "claude-sonnet-5"
    image_model: str = "gpt-image-2"

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
