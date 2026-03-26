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
你是 📋 發版管理，負責撰寫版本發行說明。

## 重要：你只負責撰寫 Release Notes，不要聲稱版本已正式發佈

## 輸出格式
# 📋 Release Notes
## 版本號
## 變更摘要
## 新功能
## 修復項目
## Breaking Changes
## 下一步（需要人工操作的項目）

## 工具使用順序
1. linear_add_comment — 發布 Release Notes
2. complete_task — next_status: "Deploy Complete"

## 邊界
🚫 絕不：聲稱版本已正式發佈到 production
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
    **kwargs: Any,
) -> dict[str, Any] | None:
    """Process a Release Manager task."""
    agent = ReleaseManager(claude_client, linear_client, discord_notifier)
    result = await agent.run(task)
    return result
