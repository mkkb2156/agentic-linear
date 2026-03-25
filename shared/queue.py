from __future__ import annotations

import json
import logging
import uuid
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)


class TaskQueue:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def enqueue(
        self,
        queue_name: str,
        agent_role: str,
        issue_id: str,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
        project_id: uuid.UUID | None = None,
    ) -> uuid.UUID | None:
        """Insert a new task. Returns task ID, or None if duplicate (idempotent)."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO agent_tasks (queue_name, agent_role, issue_id, project_id, payload, idempotency_key)
                VALUES ($1, $2, $3, $4, $5::jsonb, $6)
                ON CONFLICT (idempotency_key) DO NOTHING
                RETURNING id
                """,
                queue_name,
                agent_role,
                issue_id,
                project_id,
                json.dumps(payload),
                idempotency_key,
            )
            if row:
                await self.notify(queue_name)
                logger.info("Enqueued task %s for %s on queue %s", row["id"], agent_role, queue_name)
                return row["id"]
            logger.info("Duplicate task skipped (idempotency_key=%s)", idempotency_key)
            return None

    async def fetch_next(self, queue_name: str) -> asyncpg.Record | None:
        """Atomically claim the next pending task using SKIP LOCKED."""
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(
                """
                UPDATE agent_tasks
                SET status = 'processing', started_at = NOW()
                WHERE id = (
                    SELECT id FROM agent_tasks
                    WHERE queue_name = $1 AND status = 'pending'
                    ORDER BY created_at
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                ) RETURNING *
                """,
                queue_name,
            )

    async def complete(
        self,
        task_id: uuid.UUID,
        tokens_used: int = 0,
        model_used: str | None = None,
    ) -> None:
        """Mark a task as completed."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE agent_tasks
                SET status = 'completed', completed_at = NOW(),
                    tokens_used = $2, model_used = $3
                WHERE id = $1
                """,
                task_id,
                tokens_used,
                model_used,
            )
            logger.info("Task %s completed", task_id)

    async def fail(self, task_id: uuid.UUID, error_message: str) -> str:
        """Mark a task as failed. Returns new status ('failed' or 'dead')."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE agent_tasks
                SET status = CASE
                        WHEN retry_count + 1 >= max_retries THEN 'dead'
                        ELSE 'failed'
                    END,
                    retry_count = retry_count + 1,
                    error_message = $2,
                    completed_at = NOW()
                WHERE id = $1
                RETURNING status
                """,
                task_id,
                error_message,
            )
            new_status = row["status"] if row else "unknown"
            logger.warning("Task %s → %s: %s", task_id, new_status, error_message)
            return new_status

    async def retry_failed(self, queue_name: str) -> int:
        """Re-queue failed (not dead) tasks. Returns count of retried tasks."""
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE agent_tasks
                SET status = 'pending', started_at = NULL, completed_at = NULL, error_message = NULL
                WHERE queue_name = $1 AND status = 'failed'
                """,
                queue_name,
            )
            count = int(result.split()[-1])
            if count > 0:
                await self.notify(queue_name)
            return count

    async def notify(self, queue_name: str) -> None:
        """Send a NOTIFY on the queue channel."""
        async with self._pool.acquire() as conn:
            await conn.execute(f"NOTIFY queue_{queue_name}")

    async def setup_listen(self, queue_name: str, conn: asyncpg.Connection) -> None:
        """Subscribe to NOTIFY events for a queue on the given connection."""
        await conn.add_listener(f"queue_{queue_name}", self._on_notify)
        logger.info("Listening on queue_%s", queue_name)

    def _on_notify(self, conn: asyncpg.Connection, pid: int, channel: str, payload: str) -> None:
        """Callback for LISTEN/NOTIFY — used to wake up the worker loop."""
        logger.debug("Notification on %s (pid=%s)", channel, pid)
