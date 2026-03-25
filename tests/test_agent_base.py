"""Tests for the base agent framework and tool handling."""

import json
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.agent_base import BaseAgent
from shared.models import AgentRole
from shared.tools import PLANNING_TOOLS


class MockAgent(BaseAgent):
    """Concrete agent for testing."""

    role = AgentRole.PRODUCT_STRATEGIST
    system_prompt = "You are a test agent."
    tools = PLANNING_TOOLS


def _make_task(
    issue_id: str = "DRO-99",
    agent_role: str = "product_strategist",
    payload: dict | None = None,
) -> MagicMock:
    """Create a mock asyncpg.Record for a task."""
    if payload is None:
        payload = {
            "event": {
                "data": {
                    "id": "issue-uuid-123",
                    "identifier": issue_id,
                    "title": "Test Feature",
                    "description": "Build a test feature",
                    "state": {"id": "state-1", "name": "Strategy Complete"},
                },
            },
            "old_status": "In Progress",
            "new_status": "Strategy Complete",
        }

    task = MagicMock()
    task.__getitem__ = lambda self, key: {
        "id": uuid.uuid4(),
        "issue_id": issue_id,
        "agent_role": agent_role,
        "queue_name": "planning",
        "payload": payload,
    }[key]
    return task


@pytest.fixture
def mock_claude() -> AsyncMock:
    client = AsyncMock()
    return client


@pytest.fixture
def mock_linear() -> AsyncMock:
    client = AsyncMock()
    client.get_issue.return_value = {
        "id": "issue-uuid-123",
        "identifier": "DRO-99",
        "title": "Test Feature",
        "description": "Build a test feature",
        "state": {"id": "state-1", "name": "Strategy Complete"},
        "labels": {"nodes": []},
        "project": {"id": "proj-1", "name": "Test Project"},
    }
    client.get_issue_comments.return_value = []
    client.transition_issue.return_value = {"success": True}
    return client


@pytest.fixture
def mock_discord() -> AsyncMock:
    client = AsyncMock()
    client.send_task_started.return_value = None
    client.send_task_complete.return_value = None
    return client


@pytest.mark.asyncio
async def test_agent_completes_with_tool_use(
    mock_claude: AsyncMock, mock_linear: AsyncMock, mock_discord: AsyncMock
) -> None:
    """Test agent runs agentic loop and completes via complete_task tool."""
    # Mock Claude returning a tool_use response followed by end_turn
    tool_use_block = MagicMock()
    tool_use_block.type = "tool_use"
    tool_use_block.name = "complete_task"
    tool_use_block.id = "tool-1"
    tool_use_block.input = {"summary": "PRD created", "next_status": "Strategy Complete"}

    response = MagicMock()
    response.stop_reason = "tool_use"
    response.content = [tool_use_block]
    response.usage = MagicMock()
    response.usage.input_tokens = 100
    response.usage.output_tokens = 50

    mock_claude.execute.return_value = (response, 150, "claude-sonnet-4-6")

    agent = MockAgent(mock_claude, mock_linear, mock_discord)
    task = _make_task()

    result = await agent.run(task)

    assert result["summary"] == "PRD created"
    assert result["next_status"] == "Strategy Complete"
    assert result["tokens_used"] == 150
    assert result["model_used"] == "claude-sonnet-4-6"

    # Should have notified Discord
    mock_discord.send_task_started.assert_called_once()
    mock_discord.send_task_complete.assert_called_once()

    # Should have transitioned Linear status
    mock_linear.transition_issue.assert_called_once_with("issue-uuid-123", "Strategy Complete")


@pytest.mark.asyncio
async def test_agent_handles_text_response(
    mock_claude: AsyncMock, mock_linear: AsyncMock, mock_discord: AsyncMock
) -> None:
    """Test agent handles Claude responding with text only (no tools)."""
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "I analyzed the issue and here are my findings..."

    response = MagicMock()
    response.stop_reason = "end_turn"
    response.content = [text_block]
    response.usage = MagicMock()
    response.usage.input_tokens = 80
    response.usage.output_tokens = 30

    mock_claude.execute.return_value = (response, 110, "claude-sonnet-4-6")

    agent = MockAgent(mock_claude, mock_linear, mock_discord)
    task = _make_task()

    result = await agent.run(task)

    assert "I analyzed the issue" in result["summary"]
    assert result["next_status"] == ""  # No status transition
    mock_linear.transition_issue.assert_not_called()


@pytest.mark.asyncio
async def test_agent_executes_linear_comment_tool(
    mock_claude: AsyncMock, mock_linear: AsyncMock, mock_discord: AsyncMock
) -> None:
    """Test agent can call linear_add_comment then complete_task."""
    # First response: call linear_add_comment
    comment_block = MagicMock()
    comment_block.type = "tool_use"
    comment_block.name = "linear_add_comment"
    comment_block.id = "tool-1"
    comment_block.input = {"issue_id": "issue-uuid-123", "body": "## PRD\nThis is the PRD"}

    response1 = MagicMock()
    response1.stop_reason = "tool_use"
    response1.content = [comment_block]
    response1.usage = MagicMock()
    response1.usage.input_tokens = 100
    response1.usage.output_tokens = 50

    # Second response: call complete_task
    complete_block = MagicMock()
    complete_block.type = "tool_use"
    complete_block.name = "complete_task"
    complete_block.id = "tool-2"
    complete_block.input = {"summary": "PRD posted", "next_status": "Strategy Complete"}

    response2 = MagicMock()
    response2.stop_reason = "tool_use"
    response2.content = [complete_block]
    response2.usage = MagicMock()
    response2.usage.input_tokens = 200
    response2.usage.output_tokens = 40

    mock_claude.execute.side_effect = [
        (response1, 150, "claude-sonnet-4-6"),
        (response2, 240, "claude-sonnet-4-6"),
    ]
    mock_linear.add_comment.return_value = {"success": True}

    agent = MockAgent(mock_claude, mock_linear, mock_discord)
    task = _make_task()

    result = await agent.run(task)

    assert result["summary"] == "PRD posted"
    mock_linear.add_comment.assert_called_once_with("issue-uuid-123", "## PRD\nThis is the PRD")
    assert result["tokens_used"] == 390  # 150 + 240


@pytest.mark.asyncio
async def test_agent_includes_previous_comments(
    mock_claude: AsyncMock, mock_linear: AsyncMock, mock_discord: AsyncMock
) -> None:
    """Test that previous agent comments are included in the user message."""
    mock_linear.get_issue_comments.return_value = [
        {"user": {"name": "Product Strategist"}, "body": "## PRD\nRequirements here..."},
    ]

    # Simple text response
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "Acknowledged"

    response = MagicMock()
    response.stop_reason = "end_turn"
    response.content = [text_block]
    response.usage = MagicMock()
    response.usage.input_tokens = 200
    response.usage.output_tokens = 10

    mock_claude.execute.return_value = (response, 210, "claude-sonnet-4-6")

    agent = MockAgent(mock_claude, mock_linear, mock_discord)
    task = _make_task()

    await agent.run(task)

    # Check that the user message sent to Claude includes previous comments
    call_args = mock_claude.execute.call_args
    messages = call_args.kwargs.get("messages", call_args.args[2] if len(call_args.args) > 2 else [])
    user_content = messages[0]["content"]
    assert "Previous Agent Outputs" in user_content
    assert "Product Strategist" in user_content


@pytest.mark.asyncio
async def test_agent_handles_tool_error(
    mock_claude: AsyncMock, mock_linear: AsyncMock, mock_discord: AsyncMock
) -> None:
    """Test agent handles tool execution errors gracefully."""
    # Tool call that will fail
    comment_block = MagicMock()
    comment_block.type = "tool_use"
    comment_block.name = "linear_add_comment"
    comment_block.id = "tool-1"
    comment_block.input = {"issue_id": "bad-id", "body": "test"}

    response1 = MagicMock()
    response1.stop_reason = "tool_use"
    response1.content = [comment_block]
    response1.usage = MagicMock()
    response1.usage.input_tokens = 100
    response1.usage.output_tokens = 50

    # After error, Claude completes
    complete_block = MagicMock()
    complete_block.type = "tool_use"
    complete_block.name = "complete_task"
    complete_block.id = "tool-2"
    complete_block.input = {"summary": "Done with errors", "next_status": ""}

    response2 = MagicMock()
    response2.stop_reason = "tool_use"
    response2.content = [complete_block]
    response2.usage = MagicMock()
    response2.usage.input_tokens = 150
    response2.usage.output_tokens = 30

    mock_claude.execute.side_effect = [
        (response1, 150, "claude-sonnet-4-6"),
        (response2, 180, "claude-sonnet-4-6"),
    ]
    mock_linear.add_comment.side_effect = RuntimeError("API error")

    agent = MockAgent(mock_claude, mock_linear, mock_discord)
    task = _make_task()

    result = await agent.run(task)

    # Should still complete despite tool error
    assert result["summary"] == "Done with errors"
