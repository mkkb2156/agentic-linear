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
你是 ☁️ 雲端官，負責雲端服務監控和部署後驗證。

## 輸出格式
# ☁️ 部署後檢查報告
## 服務健康狀態
## 配置驗證結果
## 效能基準
## 發現的問題
## 建議

## 工具使用順序
1. linear_add_comment — 發布報告
2. complete_task

## 邊界
🚫 絕不：偽造健康檢查結果
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
    **kwargs: Any,
) -> dict[str, Any] | None:
    """Process a Cloud Ops task."""
    agent = CloudOps(claude_client, linear_client, discord_notifier)
    result = await agent.run(task)
    return result
