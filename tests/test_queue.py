"""Tests for the PostgreSQL task queue.

These tests require a running PostgreSQL instance.
Skip if DATABASE_URL is not available.
"""

import json
import os
import uuid

import pytest
import asyncpg

from shared.queue import TaskQueue

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/gds_agent"
)

# Skip all tests if we can't connect to the database
pytestmark = pytest.mark.asyncio


async def _get_pool() -> asyncpg.Pool:
    try:
        pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=3, timeout=5)
        # Ensure table exists
        async with pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_tasks (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    queue_name VARCHAR(50) NOT NULL,
                    agent_role VARCHAR(50) NOT NULL,
                    issue_id VARCHAR(20) NOT NULL,
                    project_id UUID,
                    payload JSONB NOT NULL DEFAULT '{}',
                    status VARCHAR(20) DEFAULT 'pending',
                    retry_count INT DEFAULT 0,
                    max_retries INT DEFAULT 3,
                    model_used VARCHAR(30),
                    tokens_used INT DEFAULT 0,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    started_at TIMESTAMPTZ,
                    completed_at TIMESTAMPTZ,
                    error_message TEXT,
                    idempotency_key VARCHAR(100) UNIQUE
                )
            """)
        return pool
    except Exception:
        pytest.skip("PostgreSQL not available")


@pytest.fixture
async def queue():
    pool = await _get_pool()
    # Clean up before each test
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM agent_tasks")
    q = TaskQueue(pool)
    yield q
    await pool.close()


async def test_enqueue_and_fetch(queue: TaskQueue) -> None:
    task_id = await queue.enqueue(
        queue_name="planning",
        agent_role="spec_architect",
        issue_id="DRO-1",
        payload={"test": True},
    )
    assert task_id is not None

    task = await queue.fetch_next("planning")
    assert task is not None
    assert task["issue_id"] == "DRO-1"
    assert task["status"] == "processing"
    assert task["agent_role"] == "spec_architect"


async def test_idempotency_rejects_duplicate(queue: TaskQueue) -> None:
    idem_key = f"test-{uuid.uuid4()}"
    id1 = await queue.enqueue(
        queue_name="planning",
        agent_role="spec_architect",
        issue_id="DRO-2",
        payload={},
        idempotency_key=idem_key,
    )
    id2 = await queue.enqueue(
        queue_name="planning",
        agent_role="spec_architect",
        issue_id="DRO-2",
        payload={},
        idempotency_key=idem_key,
    )
    assert id1 is not None
    assert id2 is None  # Duplicate rejected


async def test_complete_task(queue: TaskQueue) -> None:
    task_id = await queue.enqueue(
        queue_name="build",
        agent_role="frontend_engineer",
        issue_id="DRO-3",
        payload={},
    )
    task = await queue.fetch_next("build")
    await queue.complete(task["id"], tokens_used=150, model_used="claude-sonnet-4-6")

    # Should not be fetchable again
    next_task = await queue.fetch_next("build")
    assert next_task is None


async def test_fail_and_retry(queue: TaskQueue) -> None:
    task_id = await queue.enqueue(
        queue_name="verify",
        agent_role="qa_engineer",
        issue_id="DRO-4",
        payload={},
    )
    task = await queue.fetch_next("verify")

    # First failure
    status = await queue.fail(task["id"], "Test error")
    assert status == "failed"

    # Retry failed tasks
    retried = await queue.retry_failed("verify")
    assert retried == 1

    # Fetch again
    task = await queue.fetch_next("verify")
    assert task is not None
    assert task["retry_count"] == 1


async def test_dead_after_max_retries(queue: TaskQueue) -> None:
    task_id = await queue.enqueue(
        queue_name="ops",
        agent_role="infra_ops",
        issue_id="DRO-5",
        payload={},
    )

    # Fail 3 times (max_retries default is 3)
    for i in range(3):
        task = await queue.fetch_next("ops")
        if task is None:
            # Need to re-queue failed tasks
            await queue.retry_failed("ops")
            task = await queue.fetch_next("ops")
        assert task is not None
        status = await queue.fail(task["id"], f"Error {i+1}")

    assert status == "dead"

    # Retry should not pick up dead tasks
    retried = await queue.retry_failed("ops")
    assert retried == 0


async def test_skip_locked_concurrent(queue: TaskQueue) -> None:
    """Two concurrent fetch_next calls should get different tasks."""
    await queue.enqueue(queue_name="planning", agent_role="spec_architect", issue_id="DRO-10", payload={})
    await queue.enqueue(queue_name="planning", agent_role="spec_architect", issue_id="DRO-11", payload={})

    task1 = await queue.fetch_next("planning")
    task2 = await queue.fetch_next("planning")

    assert task1 is not None
    assert task2 is not None
    assert task1["id"] != task2["id"]
    assert {task1["issue_id"], task2["issue_id"]} == {"DRO-10", "DRO-11"}
