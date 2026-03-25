"""Base worker loop shared by all worker services."""

from __future__ import annotations

import asyncio
import logging
import signal
from typing import Any, Awaitable, Callable

import asyncpg

from shared.claude_client import ClaudeClient
from shared.config import get_settings
from shared.discord_notifier import DiscordNotifier
from shared.linear_client import LinearClient
from shared.queue import TaskQueue

logger = logging.getLogger(__name__)

AgentHandler = Callable[
    [asyncpg.Record, ClaudeClient, LinearClient, DiscordNotifier],
    Awaitable[None],
]


class BaseWorker:
    def __init__(
        self,
        queue_name: str,
        agent_registry: dict[str, AgentHandler],
        poll_interval: float = 5.0,
    ) -> None:
        self.queue_name = queue_name
        self.agent_registry = agent_registry
        self.poll_interval = poll_interval
        self._shutdown = asyncio.Event()

    async def run(self) -> None:
        settings = get_settings()

        pool = await asyncpg.create_pool(settings.database_url, min_size=2, max_size=5)
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

        # Set up LISTEN/NOTIFY
        listen_conn = await pool.acquire()
        await task_queue.setup_listen(self.queue_name, listen_conn)

        # Graceful shutdown
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._shutdown.set)

        logger.info("Worker [%s] started, polling for tasks...", self.queue_name)

        try:
            while not self._shutdown.is_set():
                task = await task_queue.fetch_next(self.queue_name)
                if task:
                    await self._process(task, task_queue, claude_client, linear_client, discord_notifier)
                else:
                    # Wait for notification or poll interval
                    try:
                        await asyncio.wait_for(self._shutdown.wait(), timeout=self.poll_interval)
                    except asyncio.TimeoutError:
                        pass
        finally:
            await pool.release(listen_conn)
            await linear_client.close()
            await claude_client.close()
            await discord_notifier.close()
            await pool.close()
            logger.info("Worker [%s] stopped", self.queue_name)

    async def _process(
        self,
        task: asyncpg.Record,
        task_queue: TaskQueue,
        claude_client: ClaudeClient,
        linear_client: LinearClient,
        discord_notifier: DiscordNotifier,
    ) -> None:
        agent_role = task["agent_role"]
        task_id = task["id"]
        handler = self.agent_registry.get(agent_role)

        if not handler:
            logger.error("No handler for agent role: %s", agent_role)
            await task_queue.fail(task_id, f"Unknown agent role: {agent_role}")
            return

        logger.info("Processing task %s with agent %s", task_id, agent_role)
        try:
            await handler(task, claude_client, linear_client, discord_notifier)
            await task_queue.complete(task_id)
        except Exception as e:
            logger.exception("Task %s failed: %s", task_id, e)
            new_status = await task_queue.fail(task_id, str(e))
            if new_status == "dead":
                await discord_notifier.send_alert(
                    agent_role=agent_role,
                    title=f"Task Dead: {task['issue_id']}",
                    description=f"Agent `{agent_role}` failed after max retries.\nError: {e}",
                )
