from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

import asyncpg
from fastapi import FastAPI

from shared.claude_client import ClaudeClient
from shared.config import get_settings
from shared.discord_notifier import DiscordNotifier
from shared.linear_client import LinearClient
from shared.queue import TaskQueue

from .discord.bot import start_bot, stop_bot
from .webhooks.linear import router as linear_router
from .webhooks.github import router as github_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()

    # Database pool
    pool = await asyncpg.create_pool(settings.database_url, min_size=2, max_size=10)
    app.state.db_pool = pool
    app.state.task_queue = TaskQueue(pool)

    # Clients
    app.state.linear_client = LinearClient(settings.linear_api_key)
    app.state.claude_client = ClaudeClient(settings.anthropic_api_key)
    app.state.discord_notifier = DiscordNotifier(
        webhook_urls={
            "agent_hub": settings.discord_webhook_url_agent_hub,
            "dashboard": settings.discord_webhook_url_dashboard,
            "alerts": settings.discord_webhook_url_alerts,
            "deploy_log": settings.discord_webhook_url_deploy_log,
        }
    )

    # Start Discord bot (non-blocking)
    if settings.discord_bot_token:
        await start_bot(settings.discord_bot_token)

    logger.info("Gateway started")
    yield

    # Cleanup
    await stop_bot()
    await app.state.linear_client.close()
    await app.state.claude_client.close()
    await app.state.discord_notifier.close()
    await pool.close()
    logger.info("Gateway stopped")


app = FastAPI(title="GDS Agent Gateway", lifespan=lifespan)

app.include_router(linear_router, prefix="/webhooks")
app.include_router(github_router, prefix="/webhooks")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
