from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/gds_agent"

    # Linear
    linear_api_key: str = ""
    linear_webhook_secret: str = ""

    # Anthropic / Claude
    anthropic_api_key: str = ""

    # Discord
    discord_bot_token: str = ""
    discord_webhook_url_agent_hub: str = ""
    discord_webhook_url_dashboard: str = ""
    discord_webhook_url_alerts: str = ""
    discord_webhook_url_deploy_log: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
