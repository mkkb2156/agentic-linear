"""Tests for the agent dispatcher."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from shared.agent_base import AgentTask
from shared.dispatcher import AgentDispatcher, _seen_keys
from shared.models import AgentRole


@pytest.fixture(autouse=True)
def clear_idempotency() -> None:
    """Clear the idempotency cache between tests."""
    _seen_keys.clear()


@pytest.fixture
def dispatcher() -> AgentDispatcher:
    return AgentDispatcher(
        claude_client=AsyncMock(),
        linear_client=AsyncMock(),
        discord_notifier=AsyncMock(),
    )


def _make_task(issue_id: str = "DRO-42") -> AgentTask:
    return AgentTask(
        issue_id=issue_id,
        agent_role="spec_architect",
        payload={"event": {"data": {"id": "uuid"}}, "old_status": "X", "new_status": "Y"},
    )


@pytest.mark.asyncio
async def test_dispatch_runs_handler(dispatcher: AgentDispatcher) -> None:
    handler = AsyncMock(return_value={"tokens_used": 100, "model_used": "sonnet"})
    dispatcher.register(AgentRole.SPEC_ARCHITECT, handler)

    task = _make_task()
    result = await dispatcher.dispatch(AgentRole.SPEC_ARCHITECT, task)

    assert result is True
    # Wait for background task
    await asyncio.sleep(0.05)
    handler.assert_called_once()


@pytest.mark.asyncio
async def test_dispatch_unknown_role_returns_false(dispatcher: AgentDispatcher) -> None:
    task = _make_task()
    result = await dispatcher.dispatch(AgentRole.SPEC_ARCHITECT, task)
    assert result is False


@pytest.mark.asyncio
async def test_idempotency_blocks_duplicate(dispatcher: AgentDispatcher) -> None:
    handler = AsyncMock(return_value=None)
    dispatcher.register(AgentRole.SPEC_ARCHITECT, handler)

    task = _make_task()
    r1 = await dispatcher.dispatch(AgentRole.SPEC_ARCHITECT, task, delivery_id="d-1")
    r2 = await dispatcher.dispatch(AgentRole.SPEC_ARCHITECT, task, delivery_id="d-1")

    assert r1 is True
    assert r2 is False  # Duplicate blocked


@pytest.mark.asyncio
async def test_different_delivery_ids_allowed(dispatcher: AgentDispatcher) -> None:
    handler = AsyncMock(return_value=None)
    dispatcher.register(AgentRole.SPEC_ARCHITECT, handler)

    task = _make_task()
    r1 = await dispatcher.dispatch(AgentRole.SPEC_ARCHITECT, task, delivery_id="d-1")
    r2 = await dispatcher.dispatch(AgentRole.SPEC_ARCHITECT, task, delivery_id="d-2")

    assert r1 is True
    assert r2 is True


@pytest.mark.asyncio
async def test_handler_error_sends_discord_alert(dispatcher: AgentDispatcher) -> None:
    handler = AsyncMock(side_effect=RuntimeError("boom"))
    dispatcher.register(AgentRole.SPEC_ARCHITECT, handler)

    task = _make_task()
    await dispatcher.dispatch(AgentRole.SPEC_ARCHITECT, task)
    await asyncio.sleep(0.05)

    dispatcher._discord.send_alert.assert_called_once()
