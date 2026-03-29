"""Standalone agent worker — consumes tasks from Redis queue.

Usage:
    python -m services.worker.main --role product_strategist
    python -m services.worker.main --role frontend_engineer

Each worker process handles one agent role, consuming tasks from its
dedicated Redis queue and executing the agent's agentic loop.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import time
from datetime import datetime, timezone
from typing import Any

logging.basicConfig(
    level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

logger = logging.getLogger(__name__)

# Agent handler registry: role → execute function
_AGENT_HANDLERS: dict[str, Any] = {
    "product_strategist": "services.planning.agents.product_strategist",
    "spec_architect": "services.planning.agents.spec_architect",
    "system_architect": "services.planning.agents.system_architect",
    "frontend_engineer": "services.build.agents.frontend_engineer",
    "backend_engineer": "services.build.agents.backend_engineer",
    "qa_engineer": "services.verify.agents.qa_engineer",
    "devops": "services.verify.agents.devops",
    "release_manager": "services.verify.agents.release_manager",
    "infra_ops": "services.ops.agents.infra_ops",
    "cloud_ops": "services.ops.agents.cloud_ops",
    "admin": "services.admin.agents.admin_agent",
}


def _load_handler(role: str) -> Any:
    """Dynamically import the execute function for the given agent role."""
    module_path = _AGENT_HANDLERS[role]
    import importlib
    module = importlib.import_module(module_path)
    return module.execute


async def run_worker(role: str) -> None:
    """Main worker loop: connect to Redis, consume tasks, execute agent."""
    from shared.config import get_settings
    from shared.claude_client import ClaudeClient
    from shared.linear_client import LinearClient
    from shared.discord_notifier import DiscordNotifier
    from shared.github_client import GitHubClient
    from shared.vercel_client import VercelClient
    from shared.redis_queue import RedisQueue
    from shared.database import Database
    from shared.agent_state import AgentStateTracker
    from shared.agent_base import AgentTask
    from shared.metrics import AgentRunRecord, HybridMetricsStore
    from shared.soul_manager import SoulManager
    from shared.project_context import ProjectContextManager
    from shared.conversation_store import ConversationStore

    settings = get_settings()
    handler = _load_handler(role)

    # Initialize clients
    claude_client = ClaudeClient(settings.anthropic_api_key)
    linear_client = LinearClient(settings.linear_api_key)
    discord_notifier = DiscordNotifier(
        webhook_urls={
            "agent_hub": settings.discord_webhook_url_agent_hub,
            "dashboard": settings.discord_webhook_url_dashboard,
            "alerts": settings.discord_webhook_url_alerts,
            "deploy_log": settings.discord_webhook_url_deploy_log,
        }
    )

    github_client = None
    if settings.github_token:
        github_client = GitHubClient(settings.github_token, owner=settings.github_repo_owner)

    vercel_client = None
    if settings.vercel_token:
        vercel_client = VercelClient(settings.vercel_token, team_id=settings.vercel_team_id)

    # Initialize infrastructure
    redis_queue = RedisQueue()
    await redis_queue.connect(settings.redis_url)

    db = None
    if settings.database_url:
        db = Database()
        await db.connect(settings.database_url)

    state_tracker = AgentStateTracker(redis_queue)
    metrics_store = HybridMetricsStore(db=db)
    soul_manager = SoulManager()
    project_context = ProjectContextManager()
    conversation_store = ConversationStore()
    conversation_store.load()

    # Set initial idle state
    await state_tracker.set_idle(role)

    logger.info("Worker started: role=%s, listening on queue:%s", role, role)

    shutdown_event = asyncio.Event()

    def _handle_signal(sig: int, _: Any) -> None:
        logger.info("Received signal %d, shutting down...", sig)
        shutdown_event.set()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    while not shutdown_event.is_set():
        # Block-wait for a task (5s timeout to check shutdown flag)
        task_data = await redis_queue.consume_task(role, timeout=5)
        if task_data is None:
            continue

        issue_id = task_data.get("issue_id", "unknown")
        logger.info("Received task: %s for issue %s", role, issue_id)

        # Build AgentTask
        payload = task_data.get("payload", {})
        payload["_conversation_store"] = conversation_store
        payload["_project_context"] = project_context
        payload["_soul_manager"] = soul_manager
        task = AgentTask(
            issue_id=issue_id,
            agent_role=role,
            payload=payload,
        )

        # Execute agent
        success = False
        error_msg = ""
        result: dict[str, Any] = {}
        start_time = time.monotonic()

        try:
            result = await handler(
                task, claude_client, linear_client, discord_notifier,
                github_client=github_client,
                vercel_client=vercel_client,
                state_tracker=state_tracker,
                db=db,
            ) or {}
            success = True
            logger.info(
                "Agent %s completed for %s: %d tokens",
                role, issue_id, result.get("tokens_used", 0),
            )
        except Exception as e:
            error_msg = str(e)
            logger.exception("Agent %s failed for %s: %s", role, issue_id, e)
            await discord_notifier.send_alert(
                agent_role=role,
                title=f"Agent Failed: {issue_id}",
                description=f"Agent `{role}` failed.\nError: {e}",
            )
        finally:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            tokens = (result or {}).get("tokens_used", 0)
            model = (result or {}).get("model_used", "")
            summary = (result or {}).get("summary", "")

            run_record = AgentRunRecord(
                agent_role=role,
                issue_id=issue_id,
                tokens_used=tokens,
                model_used=model,
                duration_ms=duration_ms,
                success=success,
                error_message=error_msg,
                timestamp=datetime.now(timezone.utc).isoformat(),
                summary=summary[:200],
            )
            await metrics_store.record_async(run_record)

    # Cleanup
    logger.info("Worker shutting down: %s", role)
    await redis_queue.close()
    if db:
        await db.close()
    await claude_client.close()
    await linear_client.close()
    await discord_notifier.close()
    if github_client:
        await github_client.close()
    if vercel_client:
        await vercel_client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent Worker")
    parser.add_argument(
        "--role",
        required=True,
        choices=list(_AGENT_HANDLERS.keys()),
        help="Agent role to run",
    )
    args = parser.parse_args()
    asyncio.run(run_worker(args.role))


if __name__ == "__main__":
    main()
