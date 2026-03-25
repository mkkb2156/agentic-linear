"""Gateway service — receives Linear/GitHub webhooks and dispatches agents.

Single service architecture: no intermediate database queue.
Linear is the source of truth for all task/issue management.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI

from shared.claude_client import ClaudeClient
from shared.config import get_settings
from shared.discord_notifier import DiscordNotifier
from shared.dispatcher import AgentDispatcher
from shared.linear_client import LinearClient

from .agents import register_all_agents
from .discord.bot import start_bot, stop_bot
from .webhooks.linear import router as linear_router
from .webhooks.github import router as github_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()

    # Clients
    linear_client = LinearClient(settings.linear_api_key)
    claude_client = ClaudeClient(settings.anthropic_api_key)
    discord_notifier = DiscordNotifier(
        webhook_urls={
            "agent_hub": settings.discord_webhook_url_agent_hub,
            "dashboard": settings.discord_webhook_url_dashboard,
            "alerts": settings.discord_webhook_url_alerts,
            "deploy_log": settings.discord_webhook_url_deploy_log,
        }
    )

    # Agent dispatcher (replaces database task queue)
    dispatcher = AgentDispatcher(claude_client, linear_client, discord_notifier)
    register_all_agents(dispatcher)

    # Store on app.state for request handlers
    app.state.linear_client = linear_client
    app.state.claude_client = claude_client
    app.state.discord_notifier = discord_notifier
    app.state.dispatcher = dispatcher

    # Start Discord bot (non-blocking)
    if settings.discord_bot_token:
        await start_bot(settings.discord_bot_token)

    logger.info("Gateway started (agents: %d registered)", len(dispatcher._registry))
    yield

    # Cleanup
    await dispatcher.shutdown()
    await stop_bot()
    await linear_client.close()
    await claude_client.close()
    await discord_notifier.close()
    logger.info("Gateway stopped")


app = FastAPI(title="GDS Agent Gateway", lifespan=lifespan)

app.include_router(linear_router, prefix="/webhooks")
app.include_router(github_router, prefix="/webhooks")


@app.get("/health")
async def health() -> dict[str, Any]:
    dispatcher = app.state.dispatcher
    return {
        "status": "ok",
        "agents_registered": len(dispatcher._registry),
        "agents_active": dispatcher.active_count,
    }
