"""Gateway service — receives Linear/GitHub webhooks, dispatches agents, serves dashboard API.

Supports two dispatch modes:
- local: agents run as asyncio background tasks (original, for dev/Railway)
- redis: tasks published to Redis queues (VPS deployment with independent workers)
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
from fastapi.middleware.cors import CORSMiddleware

from shared.agent_config import AgentConfigManager
from shared.claude_client import ClaudeClient
from shared.config import get_settings
from shared.discord_notifier import DiscordNotifier
from shared.dispatcher import AgentDispatcher
from shared.github_client import GitHubClient
from shared.linear_client import LinearClient
from shared.metrics import HybridMetricsStore, MetricsStore
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

# Dashboard API routers
from .api.agents import router as agents_api_router
from .api.metrics import router as metrics_api_router
from .api.memory import router as memory_api_router
from .api.skills import router as skills_api_router
from .api.logs import router as logs_api_router
from .api.ws import router as ws_router

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

    # ── Infrastructure (Redis + PostgreSQL) ─────────────────────────────
    redis_queue = None
    state_tracker = None
    db = None

    if settings.redis_url:
        try:
            from shared.redis_queue import RedisQueue
            redis_queue = RedisQueue()
            await redis_queue.connect(settings.redis_url)
            from shared.agent_state import AgentStateTracker
            state_tracker = AgentStateTracker(redis_queue)
        except Exception as e:
            logger.warning("Redis not available, running without live state: %s", e)
            redis_queue = None

    if settings.database_url:
        try:
            from shared.database import Database
            db = Database()
            await db.connect(settings.database_url)
        except Exception as e:
            logger.warning("Database not available, using in-memory metrics: %s", e)
            db = None

    # ── Metrics and config ──────────────────────────────────────────────
    if db:
        metrics_store: MetricsStore = HybridMetricsStore(db=db)
    else:
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

    # Agent dispatcher
    dispatcher = AgentDispatcher(
        claude_client,
        linear_client,
        discord_notifier,
        metrics_store=metrics_store,
        config_manager=config_manager,
        github_client=github_client,
        vercel_client=vercel_client,
        redis_queue=redis_queue,
        db=db,
        state_tracker=state_tracker,
        dispatch_mode=settings.dispatch_mode,
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
    app.state.redis_queue = redis_queue
    app.state.state_tracker = state_tracker
    app.state.db = db

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
        "Gateway started (agents: %d, mode: %s, redis: %s, db: %s, github: %s, vercel: %s)",
        len(dispatcher._registry),
        settings.dispatch_mode,
        "CONNECTED" if redis_queue else "OFF",
        "CONNECTED" if db else "OFF",
        "CONFIGURED" if github_client else "OFF",
        "CONFIGURED" if vercel_client else "OFF",
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
    if redis_queue:
        await redis_queue.close()
    if db:
        await db.close()
    logger.info("Gateway stopped")


app = FastAPI(title="GDS Agent Gateway", lifespan=lifespan)

# CORS for dashboard frontend
settings = get_settings()
if settings.dashboard_enabled:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins.split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Webhook routes
app.include_router(linear_router, prefix="/webhooks")
app.include_router(github_router, prefix="/webhooks")

# Dashboard API routes
app.include_router(agents_api_router)
app.include_router(metrics_api_router)
app.include_router(memory_api_router)
app.include_router(skills_api_router)
app.include_router(logs_api_router)
app.include_router(ws_router)


@app.get("/health")
async def health() -> dict[str, Any]:
    dispatcher = app.state.dispatcher
    return {
        "status": "ok",
        "agents_registered": len(dispatcher._registry),
        "agents_active": dispatcher.active_count,
        "dispatch_mode": getattr(app.state, "dispatcher", None)
        and app.state.dispatcher._dispatch_mode
        or "unknown",
        "redis": app.state.redis_queue is not None,
        "database": app.state.db is not None,
        "github_configured": app.state.github_client is not None,
        "vercel_configured": app.state.vercel_client is not None,
    }
