"""Product Strategist agent — Phase 1 stub."""

from __future__ import annotations

import logging

import asyncpg

from shared.claude_client import ClaudeClient
from shared.discord_notifier import DiscordNotifier
from shared.linear_client import LinearClient
from shared.models import AgentRole

logger = logging.getLogger(__name__)


async def execute(
    task: asyncpg.Record,
    claude_client: ClaudeClient,
    linear_client: LinearClient,
    discord_notifier: DiscordNotifier,
) -> None:
    """Process a Product Strategist task. Full implementation in Phase 2."""
    logger.info(
        "[ProductStrategist] Processing task %s for issue %s",
        task["id"],
        task["issue_id"],
    )

    await discord_notifier.send_task_complete(
        agent_role=AgentRole.PRODUCT_STRATEGIST,
        issue_id=task["issue_id"],
        summary="Product Strategist task processed (Phase 1 stub)",
    )
