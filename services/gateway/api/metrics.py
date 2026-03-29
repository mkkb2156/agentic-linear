"""Dashboard API — Metrics and token usage endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Query, Request

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("")
async def get_aggregate_metrics(
    request: Request,
    agent_role: str | None = None,
    since: str | None = Query(None, description="ISO 8601 datetime"),
) -> dict[str, Any]:
    """Aggregate metrics across all or a specific agent."""
    db = getattr(request.app.state, "db", None)
    if db:
        since_dt = datetime.fromisoformat(since) if since else None
        return await db.aggregate_runs(agent_role=agent_role, since=since_dt)

    # Fallback to in-memory metrics
    metrics_store = request.app.state.metrics_store
    return metrics_store.aggregate(agent_role=agent_role, since=since)


@router.get("/runs")
async def list_runs(
    request: Request,
    agent_role: str | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
) -> list[dict[str, Any]]:
    """List agent run history with pagination."""
    db = getattr(request.app.state, "db", None)
    if db:
        since_dt = datetime.fromisoformat(since) if since else None
        until_dt = datetime.fromisoformat(until) if until else None
        runs = await db.query_runs(
            agent_role=agent_role, since=since_dt, until=until_dt,
            limit=limit, offset=offset,
        )
        # Convert datetime objects to ISO strings for JSON
        for run in runs:
            if isinstance(run.get("created_at"), datetime):
                run["created_at"] = run["created_at"].isoformat()
        return runs

    # Fallback to in-memory
    metrics_store = request.app.state.metrics_store
    records = metrics_store.query(agent_role=agent_role, since=since, until=until)
    return [r.model_dump() for r in records[offset:offset + limit]]


@router.get("/tokens")
async def token_usage(
    request: Request,
    period: str = Query("day", pattern="^(hour|day|week|month)$"),
    agent_role: str | None = None,
    since: str | None = None,
    limit: int = Query(30, le=90),
) -> list[dict[str, Any]]:
    """Token usage grouped by time period and agent."""
    db = getattr(request.app.state, "db", None)
    if db:
        since_dt = datetime.fromisoformat(since) if since else None
        rows = await db.token_usage_by_period(
            period=period, agent_role=agent_role, since=since_dt, limit=limit,
        )
        for row in rows:
            if isinstance(row.get("period"), datetime):
                row["period"] = row["period"].isoformat()
            if isinstance(row.get("cost_usd"), (int, float)):
                row["cost_usd"] = round(float(row["cost_usd"]), 4)
        return rows

    return []


@router.get("/costs")
async def cost_breakdown(
    request: Request,
    since: str | None = None,
) -> dict[str, Any]:
    """Cost breakdown by agent and model."""
    db = getattr(request.app.state, "db", None)
    if not db:
        metrics_store = request.app.state.metrics_store
        agg = metrics_store.aggregate(since=since)
        return {"total_cost_usd": agg["estimated_cost_usd"], "by_agent": {}}

    since_dt = datetime.fromisoformat(since) if since else None
    conditions = []
    params: list[Any] = []
    idx = 1
    if since_dt:
        conditions.append(f"created_at >= ${idx}")
        params.append(since_dt)
        idx += 1
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    rows = await db.pool.fetch(
        f"""
        SELECT agent_role, model_used,
               COUNT(*) AS runs,
               SUM(tokens_used) AS tokens,
               COALESCE(SUM(
                   CASE
                       WHEN model_used = 'claude-opus-4-6'
                           THEN tokens_used * 0.075 / 1000.0
                       ELSE tokens_used * 0.015 / 1000.0
                   END
               ), 0) AS cost_usd
        FROM agent_runs {where}
        GROUP BY agent_role, model_used
        ORDER BY cost_usd DESC
        """,
        *params,
    )

    total_cost = sum(float(r["cost_usd"]) for r in rows)
    by_agent: dict[str, Any] = {}
    for r in rows:
        role = r["agent_role"]
        if role not in by_agent:
            by_agent[role] = {"runs": 0, "tokens": 0, "cost_usd": 0.0, "models": {}}
        by_agent[role]["runs"] += r["runs"]
        by_agent[role]["tokens"] += r["tokens"]
        by_agent[role]["cost_usd"] += float(r["cost_usd"])
        by_agent[role]["models"][r["model_used"]] = {
            "runs": r["runs"],
            "tokens": r["tokens"],
            "cost_usd": round(float(r["cost_usd"]), 4),
        }

    for v in by_agent.values():
        v["cost_usd"] = round(v["cost_usd"], 4)

    return {"total_cost_usd": round(total_cost, 4), "by_agent": by_agent}
