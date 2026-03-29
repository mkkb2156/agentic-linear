"""PostgreSQL async connection pool + schema management.

Uses asyncpg directly for minimal overhead. Tables store agent metrics,
structured logs, and agent run history for the dashboard.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

# Schema version for future migrations
SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INT PRIMARY KEY,
    applied_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agent_runs (
    id BIGSERIAL PRIMARY KEY,
    agent_role VARCHAR(50) NOT NULL,
    issue_id VARCHAR(100) NOT NULL,
    tokens_used INT DEFAULT 0,
    model_used VARCHAR(50) DEFAULT '',
    duration_ms INT DEFAULT 0,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT DEFAULT '',
    summary TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_runs_role ON agent_runs(agent_role);
CREATE INDEX IF NOT EXISTS idx_agent_runs_created ON agent_runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_runs_issue ON agent_runs(issue_id);

CREATE TABLE IF NOT EXISTS agent_logs (
    id BIGSERIAL PRIMARY KEY,
    agent_role VARCHAR(50) NOT NULL,
    issue_id VARCHAR(100) DEFAULT '',
    level VARCHAR(10) DEFAULT 'INFO',
    message TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_logs_role ON agent_logs(agent_role);
CREATE INDEX IF NOT EXISTS idx_agent_logs_created ON agent_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_logs_level ON agent_logs(level);

INSERT INTO schema_version (version) VALUES (1)
ON CONFLICT (version) DO NOTHING;
"""


class Database:
    """Async PostgreSQL connection pool wrapper."""

    def __init__(self) -> None:
        self._pool: asyncpg.Pool | None = None

    async def connect(self, dsn: str, min_size: int = 2, max_size: int = 10) -> None:
        self._pool = await asyncpg.create_pool(dsn, min_size=min_size, max_size=max_size)
        await self._ensure_schema()
        logger.info("Database connected (pool: %d-%d)", min_size, max_size)

    async def _ensure_schema(self) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(SCHEMA_SQL)
        logger.info("Database schema ensured (version %d)", SCHEMA_VERSION)

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            logger.info("Database connection closed")

    @property
    def pool(self) -> asyncpg.Pool:
        if not self._pool:
            raise RuntimeError("Database not connected")
        return self._pool

    # ── Agent Runs ──────────────────────────────────────────────────────

    async def insert_run(
        self,
        agent_role: str,
        issue_id: str,
        tokens_used: int = 0,
        model_used: str = "",
        duration_ms: int = 0,
        success: bool = True,
        error_message: str = "",
        summary: str = "",
    ) -> int:
        row = await self.pool.fetchrow(
            """
            INSERT INTO agent_runs
                (agent_role, issue_id, tokens_used, model_used, duration_ms,
                 success, error_message, summary)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id
            """,
            agent_role, issue_id, tokens_used, model_used, duration_ms,
            success, error_message, summary[:500],
        )
        return row["id"]

    async def query_runs(
        self,
        agent_role: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        conditions: list[str] = []
        params: list[Any] = []
        idx = 1

        if agent_role:
            conditions.append(f"agent_role = ${idx}")
            params.append(agent_role)
            idx += 1
        if since:
            conditions.append(f"created_at >= ${idx}")
            params.append(since)
            idx += 1
        if until:
            conditions.append(f"created_at <= ${idx}")
            params.append(until)
            idx += 1

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.extend([limit, offset])

        rows = await self.pool.fetch(
            f"""
            SELECT id, agent_role, issue_id, tokens_used, model_used,
                   duration_ms, success, error_message, summary, created_at
            FROM agent_runs {where}
            ORDER BY created_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}
            """,
            *params,
        )
        return [dict(r) for r in rows]

    async def aggregate_runs(
        self,
        agent_role: str | None = None,
        since: datetime | None = None,
    ) -> dict[str, Any]:
        conditions: list[str] = []
        params: list[Any] = []
        idx = 1

        if agent_role:
            conditions.append(f"agent_role = ${idx}")
            params.append(agent_role)
            idx += 1
        if since:
            conditions.append(f"created_at >= ${idx}")
            params.append(since)
            idx += 1

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        row = await self.pool.fetchrow(
            f"""
            SELECT
                COUNT(*) AS total_runs,
                COUNT(*) FILTER (WHERE success) AS successful_runs,
                COUNT(*) FILTER (WHERE NOT success) AS failed_runs,
                COALESCE(SUM(tokens_used), 0) AS total_tokens,
                COALESCE(AVG(tokens_used), 0) AS avg_tokens,
                COALESCE(AVG(duration_ms), 0) AS avg_duration_ms,
                COALESCE(SUM(
                    CASE
                        WHEN model_used = 'claude-opus-4-6'
                            THEN tokens_used * 0.075 / 1000.0
                        ELSE tokens_used * 0.015 / 1000.0
                    END
                ), 0) AS estimated_cost_usd
            FROM agent_runs {where}
            """,
            *params,
        )
        total = row["total_runs"]
        return {
            "total_runs": total,
            "successful_runs": row["successful_runs"],
            "failed_runs": row["failed_runs"],
            "success_rate": row["successful_runs"] / total if total else 0.0,
            "total_tokens": row["total_tokens"],
            "avg_tokens_per_run": float(row["avg_tokens"]),
            "avg_duration_ms": float(row["avg_duration_ms"]),
            "estimated_cost_usd": round(float(row["estimated_cost_usd"]), 4),
        }

    async def token_usage_by_period(
        self,
        period: str = "day",
        agent_role: str | None = None,
        since: datetime | None = None,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        trunc = {"hour": "hour", "day": "day", "week": "week", "month": "month"}.get(
            period, "day"
        )
        conditions: list[str] = []
        params: list[Any] = []
        idx = 1

        if agent_role:
            conditions.append(f"agent_role = ${idx}")
            params.append(agent_role)
            idx += 1
        if since:
            conditions.append(f"created_at >= ${idx}")
            params.append(since)
            idx += 1

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)

        rows = await self.pool.fetch(
            f"""
            SELECT
                DATE_TRUNC('{trunc}', created_at) AS period,
                agent_role,
                SUM(tokens_used) AS tokens,
                COUNT(*) AS runs,
                COALESCE(SUM(
                    CASE
                        WHEN model_used = 'claude-opus-4-6'
                            THEN tokens_used * 0.075 / 1000.0
                        ELSE tokens_used * 0.015 / 1000.0
                    END
                ), 0) AS cost_usd
            FROM agent_runs {where}
            GROUP BY period, agent_role
            ORDER BY period DESC
            LIMIT ${idx}
            """,
            *params,
        )
        return [dict(r) for r in rows]

    # ── Agent Logs ──────────────────────────────────────────────────────

    async def insert_log(
        self,
        agent_role: str,
        message: str,
        level: str = "INFO",
        issue_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self.pool.execute(
            """
            INSERT INTO agent_logs (agent_role, issue_id, level, message, metadata)
            VALUES ($1, $2, $3, $4, $5)
            """,
            agent_role, issue_id, level, message,
            json.dumps(metadata or {}, ensure_ascii=False),
        )

    async def query_logs(
        self,
        agent_role: str | None = None,
        level: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        conditions: list[str] = []
        params: list[Any] = []
        idx = 1

        if agent_role:
            conditions.append(f"agent_role = ${idx}")
            params.append(agent_role)
            idx += 1
        if level:
            conditions.append(f"level = ${idx}")
            params.append(level)
            idx += 1
        if since:
            conditions.append(f"created_at >= ${idx}")
            params.append(since)
            idx += 1

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.extend([limit, offset])

        rows = await self.pool.fetch(
            f"""
            SELECT id, agent_role, issue_id, level, message, metadata, created_at
            FROM agent_logs {where}
            ORDER BY created_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}
            """,
            *params,
        )
        return [dict(r) for r in rows]
