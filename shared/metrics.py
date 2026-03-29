"""Metrics persistence — records agent runs with periodic JSON flush.

No external DB dependency. In-memory with atomic file flush.
"""

from __future__ import annotations

import json
import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Cost estimation per 1K tokens (blended input/output)
COST_PER_1K_TOKENS: dict[str, float] = {
    "claude-sonnet-4-6": 0.015,
    "claude-opus-4-6": 0.075,
}

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_FLUSH_PATH = DATA_DIR / "metrics.json"


class AgentRunRecord(BaseModel):
    agent_role: str
    issue_id: str
    tokens_used: int = 0
    model_used: str = ""
    duration_ms: int = 0
    success: bool = True
    error_message: str = ""
    timestamp: str = ""  # ISO 8601
    summary: str = ""


class MetricsStore:
    def __init__(self, flush_path: Path | None = None, flush_every: int = 10) -> None:
        self._records: list[AgentRunRecord] = []
        self._flush_path = flush_path or DEFAULT_FLUSH_PATH
        self._flush_every = flush_every
        self._run_counter = 0
        self._dream_counters: dict[str, int] = {}  # role/project_id → runs since last dream

    @property
    def run_count(self) -> int:
        return self._run_counter

    def record(self, run: AgentRunRecord) -> None:
        """Append a run record. Auto-flushes every N records."""
        if not run.timestamp:
            run.timestamp = datetime.now(timezone.utc).isoformat()
        self._records.append(run)
        self._run_counter += 1

        if self._run_counter % self._flush_every == 0:
            self.flush()

    def flush(self) -> None:
        """Atomic write all records to JSON file."""
        self._flush_path.parent.mkdir(parents=True, exist_ok=True)
        data = [r.model_dump() for r in self._records]
        try:
            tmp = tempfile.NamedTemporaryFile(
                mode="w",
                dir=self._flush_path.parent,
                suffix=".tmp",
                delete=False,
            )
            json.dump(data, tmp, ensure_ascii=False, indent=2)
            tmp.close()
            Path(tmp.name).replace(self._flush_path)
            logger.info("Metrics flushed: %d records to %s", len(data), self._flush_path)
        except Exception as e:
            logger.error("Failed to flush metrics: %s", e)

    def load(self) -> None:
        """Load existing records from JSON on startup."""
        if not self._flush_path.exists():
            return
        try:
            with open(self._flush_path) as f:
                data = json.load(f)
            self._records = [AgentRunRecord(**r) for r in data]
            self._run_counter = len(self._records)
            logger.info("Loaded %d metric records from %s", len(self._records), self._flush_path)
        except Exception as e:
            logger.error("Failed to load metrics: %s", e)

    def query(
        self,
        agent_role: str | None = None,
        since: str | None = None,
        until: str | None = None,
    ) -> list[AgentRunRecord]:
        """Filter records by role and/or time range (ISO 8601 strings)."""
        results = self._records
        if agent_role:
            results = [r for r in results if r.agent_role == agent_role]
        if since:
            results = [r for r in results if r.timestamp >= since]
        if until:
            results = [r for r in results if r.timestamp <= until]
        return results

    def increment_dream_counter(self, key: str) -> int:
        self._dream_counters[key] = self._dream_counters.get(key, 0) + 1
        return self._dream_counters[key]

    def reset_dream_counter(self, key: str) -> None:
        self._dream_counters[key] = 0

    def get_dream_counter(self, key: str) -> int:
        return self._dream_counters.get(key, 0)

    def aggregate(
        self,
        agent_role: str | None = None,
        since: str | None = None,
    ) -> dict[str, Any]:
        """Compute aggregate statistics."""
        records = self.query(agent_role=agent_role, since=since)
        if not records:
            return {
                "total_runs": 0,
                "successful_runs": 0,
                "failed_runs": 0,
                "success_rate": 0.0,
                "total_tokens": 0,
                "avg_tokens_per_run": 0.0,
                "avg_duration_ms": 0.0,
                "estimated_cost_usd": 0.0,
            }

        total = len(records)
        successful = sum(1 for r in records if r.success)
        total_tokens = sum(r.tokens_used for r in records)
        total_duration = sum(r.duration_ms for r in records)

        cost = 0.0
        for r in records:
            rate = COST_PER_1K_TOKENS.get(r.model_used, 0.015)
            cost += (r.tokens_used / 1000) * rate

        return {
            "total_runs": total,
            "successful_runs": successful,
            "failed_runs": total - successful,
            "success_rate": successful / total if total else 0.0,
            "total_tokens": total_tokens,
            "avg_tokens_per_run": total_tokens / total if total else 0.0,
            "avg_duration_ms": total_duration / total if total else 0.0,
            "estimated_cost_usd": round(cost, 4),
        }


class HybridMetricsStore(MetricsStore):
    """MetricsStore that writes to both in-memory and PostgreSQL.

    Falls back to in-memory only if DB is unavailable.
    """

    def __init__(
        self,
        db: Any = None,
        flush_path: Path | None = None,
        flush_every: int = 10,
    ) -> None:
        super().__init__(flush_path=flush_path, flush_every=flush_every)
        self._db = db

    async def record_async(self, run: AgentRunRecord) -> None:
        """Record a run to both in-memory store and PostgreSQL."""
        self.record(run)  # In-memory + JSON flush
        if self._db:
            try:
                await self._db.insert_run(
                    agent_role=run.agent_role,
                    issue_id=run.issue_id,
                    tokens_used=run.tokens_used,
                    model_used=run.model_used,
                    duration_ms=run.duration_ms,
                    success=run.success,
                    error_message=run.error_message,
                    summary=run.summary,
                )
            except Exception as e:
                logger.error("Failed to write metrics to DB: %s", e)
