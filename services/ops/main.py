"""Ops worker (Cron) — handles Infra Ops, Cloud Ops."""

from __future__ import annotations

import asyncio
import logging

import asyncpg

from shared.claude_client import ClaudeClient
from shared.config import get_settings
from shared.discord_notifier import DiscordNotifier
from shared.linear_client import LinearClient
from shared.models import QueueName
from shared.queue import TaskQueue

from .agents import AGENT_REGISTRY

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    """
    Ops worker runs as a cron job (every 15 min on Railway).
    Processes all pending ops tasks then exits.
    """
    settings = get_settings()
    pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=3)
    task_queue = TaskQueue(pool)
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

    processed = 0
    while True:
        task = await task_queue.fetch_next(QueueName.OPS)
        if not task:
            break

        agent_role = task["agent_role"]
        handler = AGENT_REGISTRY.get(agent_role)

        if not handler:
            logger.error("No handler for agent role: %s", agent_role)
            await task_queue.fail(task["id"], f"Unknown agent role: {agent_role}")
            continue

        try:
            await handler(task, claude_client, linear_client, discord_notifier)
            await task_queue.complete(task["id"])
            processed += 1
        except Exception as e:
            logger.exception("Task %s failed: %s", task["id"], e)
            await task_queue.fail(task["id"], str(e))

    logger.info("Ops worker finished: %d tasks processed", processed)

    await linear_client.close()
    await claude_client.close()
    await discord_notifier.close()
    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
