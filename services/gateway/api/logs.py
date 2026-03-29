"""Dashboard API — Logs viewing endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query, Request

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("")
async def get_logs(
    request: Request,
    agent_role: str | None = None,
    level: str | None = None,
    since: str | None = None,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
) -> list[dict[str, Any]]:
    """Query structured agent logs from PostgreSQL."""
    db = getattr(request.app.state, "db", None)
    if not db:
        return []

    since_dt = datetime.fromisoformat(since) if since else None
    logs = await db.query_logs(
        agent_role=agent_role, level=level, since=since_dt,
        limit=limit, offset=offset,
    )
    for log in logs:
        if isinstance(log.get("created_at"), datetime):
            log["created_at"] = log["created_at"].isoformat()
        if isinstance(log.get("metadata"), str):
            import json
            try:
                log["metadata"] = json.loads(log["metadata"])
            except (json.JSONDecodeError, TypeError):
                pass
    return logs


@router.get("/learning")
async def get_learning_log(request: Request) -> dict[str, Any]:
    """Read the learning log file."""
    config_manager = request.app.state.config_manager
    content = config_manager.read_learnings()
    lines = content.strip().split("\n") if content else []
    return {
        "content": content,
        "line_count": len(lines),
        "recent": lines[-20:] if lines else [],
    }
