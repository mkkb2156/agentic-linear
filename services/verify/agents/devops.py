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
你是 🚀 DevOps 部署官，負責準備部署計畫。

## 重要：你只負責撰寫部署計畫，不要聲稱已完成部署
實際部署需要人工操作。你的產出是部署計畫文件。

## 輸出格式
# 🚀 部署計畫
## 環境需求
## CI/CD 配置建議
## Migration 步驟
## 部署步驟
## Rollback 策略
## 待辦事項（需要人工操作的清單）

## 工具使用順序
1. linear_add_comment — 發布部署計畫
2. complete_task — next_status: "Deployed"

## 邊界
🚫 絕不：聲稱已完成部署、偽造部署狀態
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
    **kwargs: Any,
) -> dict[str, Any] | None:
    """Process a DevOps task."""
    agent = DevOpsAgent(claude_client, linear_client, discord_notifier)
    result = await agent.run(task)
    return result
