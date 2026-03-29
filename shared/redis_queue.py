"""Redis-based task queue and pub/sub for agent communication.

Gateway publishes tasks to per-agent queues. Workers consume via BRPOP.
Real-time events (agent status changes) broadcast via pub/sub.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

# Queue key pattern: queue:{agent_role}
QUEUE_PREFIX = "queue:"
# Pub/sub channel for dashboard real-time events
EVENT_CHANNEL = "agent:events"
# Hash key for live agent states
STATE_KEY = "agent:states"


class RedisQueue:
    """Redis task queue + pub/sub for agent dispatch and real-time events."""

    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = None
        self._pubsub: aioredis.client.PubSub | None = None

    async def connect(self, url: str = "redis://localhost:6379") -> None:
        self._redis = aioredis.from_url(url, decode_responses=True)
        await self._redis.ping()
        logger.info("Redis connected: %s", url)

    async def close(self) -> None:
        if self._pubsub:
            await self._pubsub.close()
        if self._redis:
            await self._redis.close()
            logger.info("Redis connection closed")

    @property
    def client(self) -> aioredis.Redis:
        if not self._redis:
            raise RuntimeError("Redis not connected")
        return self._redis

    # ── Task Queue ──────────────────────────────────────────────────────

    async def publish_task(self, agent_role: str, task_data: dict[str, Any]) -> None:
        """Push a task to the agent's queue."""
        key = f"{QUEUE_PREFIX}{agent_role}"
        payload = json.dumps(task_data, ensure_ascii=False, default=str)
        await self.client.lpush(key, payload)
        logger.info("Task published to %s", key)

    async def consume_task(
        self, agent_role: str, timeout: int = 0
    ) -> dict[str, Any] | None:
        """Block-wait for a task from the agent's queue. Returns None on timeout."""
        key = f"{QUEUE_PREFIX}{agent_role}"
        result = await self.client.brpop(key, timeout=timeout)
        if result is None:
            return None
        _, payload = result
        return json.loads(payload)

    async def queue_length(self, agent_role: str) -> int:
        key = f"{QUEUE_PREFIX}{agent_role}"
        return await self.client.llen(key)

    # ── Agent State (live status for dashboard) ─────────────────────────

    async def set_agent_state(self, agent_role: str, state: dict[str, Any]) -> None:
        """Update an agent's live state (displayed on dashboard)."""
        payload = json.dumps(state, ensure_ascii=False, default=str)
        await self.client.hset(STATE_KEY, agent_role, payload)

    async def get_agent_state(self, agent_role: str) -> dict[str, Any] | None:
        raw = await self.client.hget(STATE_KEY, agent_role)
        if raw is None:
            return None
        return json.loads(raw)

    async def get_all_agent_states(self) -> dict[str, dict[str, Any]]:
        raw = await self.client.hgetall(STATE_KEY)
        return {role: json.loads(data) for role, data in raw.items()}

    # ── Pub/Sub (real-time events for WebSocket) ────────────────────────

    async def publish_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Publish a real-time event to all dashboard subscribers."""
        payload = json.dumps(
            {"type": event_type, "data": data},
            ensure_ascii=False,
            default=str,
        )
        await self.client.publish(EVENT_CHANNEL, payload)

    async def subscribe_events(self) -> aioredis.client.PubSub:
        """Subscribe to real-time agent events. Returns PubSub instance."""
        pubsub = self.client.pubsub()
        await pubsub.subscribe(EVENT_CHANNEL)
        return pubsub
