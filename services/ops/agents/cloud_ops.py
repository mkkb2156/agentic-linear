"""Cloud Ops agent — manages cloud configuration and post-deployment checks."""

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
You are the ☁️ Cloud Ops agent for the Drone168 development team.

## Your Role
You verify cloud configurations, perform post-deployment health checks, and \
ensure production environments are properly configured.

## Your Responsibilities
1. **Check** post-deployment health of services
2. **Verify** cloud configuration:
   - Environment variables are set correctly
   - DNS and routing are configured
   - SSL certificates are valid
   - Resource limits are appropriate
3. **Post findings** as a Linear comment
4. **Notify** via Discord deploy_log channel
5. **Complete** by calling complete_task with a summary

## Guidelines
- Run health checks against all deployed endpoints
- Verify database connectivity and migration status
- Check for configuration drift between environments
- Report any security misconfigurations
"""


class CloudOps(BaseAgent):
    role = AgentRole.CLOUD_OPS
    system_prompt = SYSTEM_PROMPT
    tools = VERIFY_TOOLS


async def execute(
    task: AgentTask,
    claude_client: ClaudeClient,
    linear_client: LinearClient,
    discord_notifier: DiscordNotifier,
) -> dict[str, Any] | None:
    """Process a Cloud Ops task."""
    agent = CloudOps(claude_client, linear_client, discord_notifier)
    result = await agent.run(task)
    return result
