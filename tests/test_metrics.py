"""Tests for MetricsStore."""

import json
from pathlib import Path

import pytest

from shared.metrics import AgentRunRecord, MetricsStore


@pytest.fixture
def tmp_metrics(tmp_path: Path) -> MetricsStore:
    return MetricsStore(flush_path=tmp_path / "metrics.json", flush_every=5)


def _make_record(**overrides) -> AgentRunRecord:
    defaults = {
        "agent_role": "spec_architect",
        "issue_id": "DRO-42",
        "tokens_used": 5000,
        "model_used": "claude-sonnet-4-6",
        "duration_ms": 30000,
        "success": True,
        "timestamp": "2026-03-25T10:00:00+00:00",
        "summary": "Test run",
    }
    defaults.update(overrides)
    return AgentRunRecord(**defaults)


def test_record_and_query(tmp_metrics: MetricsStore) -> None:
    tmp_metrics.record(_make_record())
    tmp_metrics.record(_make_record(agent_role="frontend_engineer"))

    assert tmp_metrics.run_count == 2
    assert len(tmp_metrics.query()) == 2
    assert len(tmp_metrics.query(agent_role="spec_architect")) == 1


def test_aggregate_computes_correctly(tmp_metrics: MetricsStore) -> None:
    tmp_metrics.record(_make_record(tokens_used=1000, success=True))
    tmp_metrics.record(_make_record(tokens_used=3000, success=True))
    tmp_metrics.record(_make_record(tokens_used=2000, success=False, error_message="fail"))

    agg = tmp_metrics.aggregate()
    assert agg["total_runs"] == 3
    assert agg["successful_runs"] == 2
    assert agg["failed_runs"] == 1
    assert abs(agg["success_rate"] - 2 / 3) < 0.01
    assert agg["total_tokens"] == 6000
    assert agg["avg_tokens_per_run"] == 2000.0
    assert agg["estimated_cost_usd"] > 0


def test_flush_and_load_roundtrip(tmp_path: Path) -> None:
    store1 = MetricsStore(flush_path=tmp_path / "m.json")
    store1.record(_make_record())
    store1.record(_make_record(agent_role="devops"))
    store1.flush()

    assert (tmp_path / "m.json").exists()
    data = json.loads((tmp_path / "m.json").read_text())
    assert len(data) == 2

    store2 = MetricsStore(flush_path=tmp_path / "m.json")
    store2.load()
    assert store2.run_count == 2
    assert len(store2.query(agent_role="devops")) == 1


def test_query_filters_by_time(tmp_metrics: MetricsStore) -> None:
    tmp_metrics.record(_make_record(timestamp="2026-03-24T00:00:00+00:00"))
    tmp_metrics.record(_make_record(timestamp="2026-03-25T12:00:00+00:00"))
    tmp_metrics.record(_make_record(timestamp="2026-03-26T00:00:00+00:00"))

    results = tmp_metrics.query(since="2026-03-25T00:00:00+00:00")
    assert len(results) == 2

    results = tmp_metrics.query(until="2026-03-25T00:00:00+00:00")
    assert len(results) == 1


def test_run_counter_increments(tmp_metrics: MetricsStore) -> None:
    assert tmp_metrics.run_count == 0
    for i in range(7):
        tmp_metrics.record(_make_record())
    assert tmp_metrics.run_count == 7
