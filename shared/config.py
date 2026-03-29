from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
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

    # GitHub
    github_token: str = ""
    github_repo_owner: str = ""  # Agent auto-resolves repos; owner used as default prefix

    # Vercel
    vercel_token: str = ""
    vercel_team_id: str = ""

    # Supabase Management
    supabase_access_token: str = ""

    # Conversational agent settings
    listen_channels: str = "project-requests,agent-war-room"
    agent_ask_timeout_minutes: int = 30
    dream_soul_threshold: int = 10
    dream_project_threshold: int = 5

    # Infrastructure (VPS deployment)
    redis_url: str = "redis://localhost:6379"
    database_url: str = ""  # PostgreSQL DSN, e.g. postgresql://user:pass@host/db
    dispatch_mode: str = "local"  # "local" (asyncio) or "redis" (queue)

    # Dashboard
    dashboard_enabled: bool = True
    cors_origins: str = "http://localhost:3000"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
