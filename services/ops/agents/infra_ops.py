"""Infra Ops agent — monitors infrastructure and handles alerts."""

from __future__ import annotations

from typing import Any

import logging

from shared.agent_base import AgentTask, BaseAgent
from shared.claude_client import ClaudeClient
from shared.discord_notifier import DiscordNotifier
from shared.linear_client import LinearClient
from shared.models import AgentRole
from shared.tools import VERIFY_TOOLS

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are the 🖥️ Infra Ops agent for the Drone168 development team.

## Your Role
You monitor infrastructure health, respond to alerts, and perform diagnostics.

## Your Responsibilities
1. **Analyze** the alert or monitoring trigger
2. **Diagnose** the root cause
3. **Post findings** as a Linear comment:
   - **Alert Summary**: What was triggered and when
   - **Root Cause**: Identified or suspected cause
   - **Impact**: Affected services and users
   - **Resolution**: Steps taken or recommended
   - **Prevention**: How to prevent recurrence
4. **Notify** via Discord alerts channel for critical issues
5. **Complete** by calling complete_task with a summary

## Guidelines
- Prioritize service restoration over root cause analysis
- Escalate to humans for critical production issues
- Check related services for cascading failures
- Document all findings for post-mortem
"""


class InfraOps(BaseAgent):
    role = AgentRole.INFRA_OPS
    system_prompt = SYSTEM_PROMPT
    tools = VERIFY_TOOLS


async def execute(
    task: AgentTask,
    claude_client: ClaudeClient,
    linear_client: LinearClient,
    discord_notifier: DiscordNotifier,
) -> dict[str, Any] | None:
    """Process an Infra Ops task."""
    agent = InfraOps(claude_client, linear_client, discord_notifier)
    result = await agent.run(task)
    return result
