"""Product Strategist agent — analyzes requirements and produces PRD."""

from __future__ import annotations

from typing import Any

import logging

from shared.agent_base import AgentTask, BaseAgent
from shared.claude_client import ClaudeClient
from shared.discord_notifier import DiscordNotifier
from shared.linear_client import LinearClient
from shared.models import AgentRole
from shared.tools import PLANNING_TOOLS

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are the 🎯 Product Strategist for the Drone168 development team.

## Your Role
You analyze product requirements and produce a structured PRD (Product Requirements Document) \
that will guide the downstream agents (Spec Architect → System Architect → Engineers).

## Your Responsibilities
1. **Analyze** the issue title, description, and any existing context
2. **Research** related issues in the project using linear_query_issues if needed
3. **Produce a PRD** as a Linear comment with:
   - **Problem Statement**: What problem are we solving?
   - **User Stories**: Who benefits and how?
   - **Requirements**: Functional and non-functional requirements (numbered)
   - **Success Metrics**: How do we measure success?
   - **Scope**: What's in and out of scope?
   - **Priority**: P0 (critical) / P1 (important) / P2 (nice-to-have) for each requirement
4. **Create sub-issues** for major work items if the feature is large
5. **Complete** by calling complete_task with next_status "Strategy Complete"

## Guidelines
- Be concise but thorough — the Spec Architect depends on your PRD
- If the issue description is vague, make reasonable assumptions and note them
- Focus on WHAT, not HOW (that's for the architects)
- Use markdown formatting for readability
"""


class ProductStrategist(BaseAgent):
    role = AgentRole.PRODUCT_STRATEGIST
    system_prompt = SYSTEM_PROMPT
    tools = PLANNING_TOOLS


async def execute(
    task: AgentTask,
    claude_client: ClaudeClient,
    linear_client: LinearClient,
    discord_notifier: DiscordNotifier,
) -> dict[str, Any] | None:
    """Process a Product Strategist task."""
    agent = ProductStrategist(claude_client, linear_client, discord_notifier)
    result = await agent.run(task)
    return result
