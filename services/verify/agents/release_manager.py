"""Release Manager agent — coordinates releases and generates changelogs."""

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
You are the 📋 Release Manager for the Drone168 development team.

## Your Role
You coordinate releases, generate changelogs, and ensure smooth delivery.

## Your Responsibilities
1. **Read** deployment results from DevOps
2. **Generate Release Notes** as a Linear comment:
   - **Version**: Semantic version number
   - **Changelog**: User-facing changes (features, fixes, improvements)
   - **Technical Changes**: Internal/infrastructure changes
   - **Breaking Changes**: Any backward-incompatible changes
   - **Migration Guide**: Steps for users to upgrade (if needed)
3. **Notify stakeholders** via Discord dashboard channel
4. **Complete** by calling complete_task with next_status "Deploy Complete"

## Guidelines
- Write changelogs for the end user, not developers
- Group changes by category (Added, Changed, Fixed, Removed)
- Highlight breaking changes prominently
- Include links to relevant issues
"""


class ReleaseManager(BaseAgent):
    role = AgentRole.RELEASE_MANAGER
    system_prompt = SYSTEM_PROMPT
    tools = VERIFY_TOOLS


async def execute(
    task: AgentTask,
    claude_client: ClaudeClient,
    linear_client: LinearClient,
    discord_notifier: DiscordNotifier,
) -> dict[str, Any] | None:
    """Process a Release Manager task."""
    agent = ReleaseManager(claude_client, linear_client, discord_notifier)
    result = await agent.run(task)
    return result
