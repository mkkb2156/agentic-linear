"""Gateway service — receives Linear/GitHub webhooks and dispatches agents.

Single service architecture: no intermediate database queue.
Linear is the source of truth for all task/issue management.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

# Configure root logger so all application loggers output to stdout
logging.basicConfig(
    level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
from typing import Any, AsyncIterator

from fastapi import FastAPI

from shared.agent_config import AgentConfigManager
from shared.claude_client import ClaudeClient
from shared.config import get_settings
from shared.discord_notifier import DiscordNotifier
from shared.dispatcher import AgentDispatcher
from shared.github_client import GitHubClient
from shared.linear_client import LinearClient
from shared.metrics import MetricsStore
from shared.vercel_client import VercelClient

from .agents import register_all_agents
from .discord.bot import start_bot, stop_bot
from .webhooks.linear import router as linear_router
from .webhooks.github import router as github_router
from shared.conversation_store import ConversationStore
from shared.soul_manager import SoulManager
from shared.project_context import ProjectContextManager
from shared.dream import DreamConsolidator
from .discord.intent_router import IntentRouter
from .discord.gatherer import MultiTurnGatherer

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

    # GitHub client (optional)
    github_client: GitHubClient | None = None
    if settings.github_token:
        github_client = GitHubClient(settings.github_token, owner=settings.github_repo_owner)

    # Vercel client (optional)
    vercel_client: VercelClient | None = None
    if settings.vercel_token:
        vercel_client = VercelClient(settings.vercel_token, team_id=settings.vercel_team_id)

    # Metrics and config
    metrics_store = MetricsStore()
    metrics_store.load()
    config_manager = AgentConfigManager()

    # Conversation + memory components
    conversation_store = ConversationStore()
    conversation_store.load()
    soul_manager = SoulManager()
    project_context_manager = ProjectContextManager()
    dream_consolidator = DreamConsolidator(
        api_key=settings.anthropic_api_key,
        soul_manager=soul_manager,
        project_context_manager=project_context_manager,
        learnings_reader=config_manager.read_learnings,
    )
    intent_router = IntentRouter(api_key=settings.anthropic_api_key)
    gatherer = MultiTurnGatherer(
        api_key=settings.anthropic_api_key,
        conversation_store=conversation_store,
    )

    # Agent dispatcher (replaces database task queue)
    dispatcher = AgentDispatcher(
        claude_client,
        linear_client,
        discord_notifier,
        metrics_store=metrics_store,
        config_manager=config_manager,
        github_client=github_client,
        vercel_client=vercel_client,
    )
    register_all_agents(dispatcher)

    dispatcher.set_memory_components(
        conversation_store=conversation_store,
        soul_manager=soul_manager,
        project_context=project_context_manager,
        dream_consolidator=dream_consolidator,
    )

    # Store on app.state for request handlers
    app.state.linear_client = linear_client
    app.state.claude_client = claude_client
    app.state.discord_notifier = discord_notifier
    app.state.dispatcher = dispatcher
    app.state.github_client = github_client
    app.state.vercel_client = vercel_client
    app.state.metrics_store = metrics_store
    app.state.config_manager = config_manager
    app.state.conversation_store = conversation_store
    app.state.soul_manager = soul_manager
    app.state.project_context_manager = project_context_manager
    app.state.dream_consolidator = dream_consolidator

    # Start Discord bot (non-blocking)
    if settings.discord_bot_token:
        await start_bot(
            settings.discord_bot_token,
            linear_client=linear_client,
            claude_client=claude_client,
            discord_notifier=discord_notifier,
            dispatcher=dispatcher,
            github_client=github_client,
            metrics_store=metrics_store,
            config_manager=config_manager,
            conversation_store=conversation_store,
            intent_router=intent_router,
            gatherer=gatherer,
        )

    logger.info(
        "Gateway started (agents: %d, github: %s, vercel: %s)",
        len(dispatcher._registry),
        "CONFIGURED" if github_client else "NOT CONFIGURED",
        "CONFIGURED" if vercel_client else "NOT CONFIGURED",
    )
    yield

    # Cleanup
    metrics_store.flush()
    await dispatcher.shutdown()
    await stop_bot()
    await linear_client.close()
    await claude_client.close()
    await discord_notifier.close()
    if github_client:
        await github_client.close()
    if vercel_client:
        await vercel_client.close()
    await intent_router.close()
    await gatherer.close()
    await dream_consolidator.close()
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
        "github_configured": app.state.github_client is not None,
        "vercel_configured": app.state.vercel_client is not None,
    }
