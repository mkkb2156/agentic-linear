"""Release Manager agent — Phase 1 stub."""

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
    """Process a Release Manager task. Full implementation in Phase 3."""
    logger.info(
        "[ReleaseManager] Processing task %s for issue %s",
        task["id"],
        task["issue_id"],
    )

    await discord_notifier.send_task_complete(
        agent_role=AgentRole.RELEASE_MANAGER,
        issue_id=task["issue_id"],
        summary="Release Manager task processed (Phase 1 stub)",
    )
