"""Centralized application settings loaded from environment variables.

All external API keys, URLs, and runtime secrets are pulled from the process
environment (or a local ``.env`` file in development) through this module.
Modules should import ``settings`` once at module load time or call
``get_settings()`` when they need values.
"""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for Bright Sunshine / Signal Raccoon."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Shared auth secret used by Railway and callers (e.g. Hermes).
    app_secret: str = ""

    # Apollo API
    apollo_api_key: str = ""
    apollo_enrich_url: str = "https://api.apollo.io/v1/organizations/enrich"

    # DeepSeek API (used by summarizer and intent analyzer).
    # Typed as SecretStr to satisfy ChatDeepSeek's api_key signature and to keep
    # the key masked in logs / dumps.
    deepseek_api_key: SecretStr = SecretStr("")

    # Tavily API (primary news search).
    tavily_api_key: str = ""

    # Parallel.ai API (primary article extraction).
    parallel_api_key: str = ""
    parallel_api_url: str = "https://api.parallel.ai/v1/extract"

    # Optional integrations.
    slack_webhook_url: str = ""
    slack_signing_secret: str = ""
    airtable_token: str = ""


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance.

    ``lru_cache`` ensures we only read and validate the environment once per
    process, which keeps startup fast and avoids repeated filesystem reads.
    """
    return Settings()


# Convenience export for modules that want settings at import time.
settings = get_settings()
