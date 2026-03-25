"""Tests for the event routing engine."""

import pytest
from unittest.mock import AsyncMock

from shared.models import AgentRole, LinearWebhookPayload
from services.gateway.router import EventRouter


@pytest.fixture
def mock_dispatcher() -> AsyncMock:
    dispatcher = AsyncMock()
    dispatcher.dispatch = AsyncMock(return_value=True)
    return dispatcher


@pytest.fixture
def router(mock_dispatcher: AsyncMock) -> EventRouter:
    return EventRouter(mock_dispatcher)


def _make_event(
    old_status: str,
    new_status: str,
    issue_id: str = "DRO-42",
) -> LinearWebhookPayload:
    return LinearWebhookPayload(
        action="update",
        type="Issue",
        data={
            "id": "issue-uuid",
            "identifier": issue_id,
            "state": {"id": "state-id", "name": new_status},
        },
        updatedFrom={"state": {"id": "old-state-id", "name": old_status}},
    )


@pytest.mark.asyncio
async def test_strategy_complete_routes_to_spec_architect(
    router: EventRouter, mock_dispatcher: AsyncMock
) -> None:
    event = _make_event("In Progress", "Strategy Complete")
    count = await router.route(event, delivery_id="delivery-1")

    assert count == 1
    mock_dispatcher.dispatch.assert_called_once()
    call_kwargs = mock_dispatcher.dispatch.call_args
    assert call_kwargs.kwargs["agent_role"] == AgentRole.SPEC_ARCHITECT


@pytest.mark.asyncio
async def test_architecture_complete_triggers_parallel_agents(
    router: EventRouter, mock_dispatcher: AsyncMock
) -> None:
    event = _make_event("Spec Complete", "Architecture Complete")
    count = await router.route(event, delivery_id="delivery-2")

    assert count == 2
    assert mock_dispatcher.dispatch.call_count == 2

    roles = [call.kwargs["agent_role"] for call in mock_dispatcher.dispatch.call_args_list]
    assert AgentRole.FRONTEND_ENGINEER in roles
    assert AgentRole.BACKEND_ENGINEER in roles


@pytest.mark.asyncio
async def test_backward_transition_blocked(
    router: EventRouter, mock_dispatcher: AsyncMock
) -> None:
    # Architecture Complete → Strategy Complete is backward
    event = _make_event("Architecture Complete", "Strategy Complete")
    count = await router.route(event, delivery_id="delivery-3")

    assert count == 0
    mock_dispatcher.dispatch.assert_not_called()


@pytest.mark.asyncio
async def test_non_update_action_ignored(
    router: EventRouter, mock_dispatcher: AsyncMock
) -> None:
    event = LinearWebhookPayload(
        action="create",
        type="Issue",
        data={"id": "issue-uuid", "state": {"name": "Strategy Complete"}},
    )
    count = await router.route(event)
    assert count == 0


@pytest.mark.asyncio
async def test_non_issue_type_ignored(
    router: EventRouter, mock_dispatcher: AsyncMock
) -> None:
    event = LinearWebhookPayload(
        action="update",
        type="Comment",
        data={"id": "comment-uuid"},
        updatedFrom={"body": "old text"},
    )
    count = await router.route(event)
    assert count == 0


@pytest.mark.asyncio
async def test_unknown_status_ignored(
    router: EventRouter, mock_dispatcher: AsyncMock
) -> None:
    event = _make_event("In Progress", "Some Random Status")
    count = await router.route(event, delivery_id="delivery-4")
    assert count == 0


@pytest.mark.asyncio
async def test_delivery_id_passed_to_dispatcher(
    router: EventRouter, mock_dispatcher: AsyncMock
) -> None:
    event = _make_event("In Progress", "Strategy Complete")
    await router.route(event, delivery_id="abc-123")

    call_kwargs = mock_dispatcher.dispatch.call_args.kwargs
    assert call_kwargs["delivery_id"] == "abc-123"


@pytest.mark.asyncio
async def test_all_pipeline_transitions(
    router: EventRouter, mock_dispatcher: AsyncMock
) -> None:
    """Verify all defined transitions produce tasks."""
    transitions = [
        ("In Progress", "Strategy Complete", 1),
        ("Strategy Complete", "Spec Complete", 1),
        ("Spec Complete", "Architecture Complete", 2),  # parallel
        ("Architecture Complete", "Implementation Done", 1),
        ("Implementation Done", "QA Passed", 1),
        ("QA Passed", "Deployed", 1),
        ("Deployed", "Deploy Complete", 1),
    ]

    for old, new, expected_count in transitions:
        mock_dispatcher.dispatch.reset_mock()
        mock_dispatcher.dispatch.return_value = True
        event = _make_event(old, new)
        count = await router.route(event)
        assert count == expected_count, f"Failed for {old} → {new}: expected {expected_count}, got {count}"
