"""Agent live state tracker — reports real-time status via Redis.

Used by BaseAgent to report execution progress, and by the dashboard
to display which agents are active, their current turn, tokens used, etc.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class AgentStateTracker:
    """Tracks agent execution state in Redis for dashboard visibility."""

    def __init__(self, redis_queue: Any | None = None) -> None:
        self._redis = redis_queue

    async def set_running(
        self,
        agent_role: str,
        issue_id: str,
        issue_title: str = "",
    ) -> None:
        if not self._redis:
            return
        await self._redis.set_agent_state(agent_role, {
            "status": "running",
            "issue_id": issue_id,
            "issue_title": issue_title,
            "current_turn": 0,
            "tokens_used": 0,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        await self._redis.publish_event("agent_started", {
            "agent_role": agent_role,
            "issue_id": issue_id,
            "issue_title": issue_title,
        })

    async def update_turn(
        self,
        agent_role: str,
        turn: int,
        tokens_used: int,
        tool_name: str = "",
    ) -> None:
        if not self._redis:
            return
        state = await self._redis.get_agent_state(agent_role) or {}
        state.update({
            "current_turn": turn,
            "tokens_used": tokens_used,
            "last_tool": tool_name,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        await self._redis.set_agent_state(agent_role, state)

    async def set_completed(
        self,
        agent_role: str,
        issue_id: str,
        tokens_used: int,
        summary: str = "",
        success: bool = True,
    ) -> None:
        if not self._redis:
            return
        status = "idle" if success else "error"
        await self._redis.set_agent_state(agent_role, {
            "status": status,
            "last_issue_id": issue_id,
            "last_tokens": tokens_used,
            "last_summary": summary[:200],
            "last_success": success,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        await self._redis.publish_event("agent_completed", {
            "agent_role": agent_role,
            "issue_id": issue_id,
            "tokens_used": tokens_used,
            "success": success,
            "summary": summary[:200],
        })

    async def set_idle(self, agent_role: str) -> None:
        if not self._redis:
            return
        await self._redis.set_agent_state(agent_role, {
            "status": "idle",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })

    async def get_all(self) -> dict[str, dict[str, Any]]:
        if not self._redis:
            return {}
        return await self._redis.get_all_agent_states()
