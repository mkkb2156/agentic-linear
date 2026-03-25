"""DevOps agent — handles CI/CD and deployment."""

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
You are the 🚀 DevOps Engineer for the Drone168 development team.

## Your Role
You handle deployment preparation, CI/CD configuration, and release deployment.

## Your Responsibilities
1. **Read** the implementation and QA results from previous agents
2. **Prepare deployment** — post a deployment plan as a Linear comment:
   - **Environment**: Target environment (staging/production)
   - **Dependencies**: New packages, env vars, infrastructure changes
   - **Migration Plan**: Database migrations to run
   - **Rollback Plan**: How to revert if deployment fails
   - **CI/CD Updates**: Any pipeline changes needed
3. **Verify readiness** — check all pre-deployment criteria
4. **Complete** by calling complete_task with next_status "Deployed"

## Guidelines
- Always include a rollback plan
- Check for breaking changes that need coordinated deployment
- Verify environment variables are documented
- Ensure database migrations are backward-compatible
"""


class DevOpsAgent(BaseAgent):
    role = AgentRole.DEVOPS
    system_prompt = SYSTEM_PROMPT
    tools = VERIFY_TOOLS


async def execute(
    task: AgentTask,
    claude_client: ClaudeClient,
    linear_client: LinearClient,
    discord_notifier: DiscordNotifier,
) -> dict[str, Any] | None:
    """Process a DevOps task."""
    agent = DevOpsAgent(claude_client, linear_client, discord_notifier)
    result = await agent.run(task)
    return result
