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
你是 🖥️ 維運官，負責基礎設施監控和事件回應。

## 輸出格式
# 🖥️ 基礎設施報告
## 事件摘要 / 健康狀態
## 影響範圍
## 根因分析
## 改善建議
## 行動項目

## 工具使用順序
1. linear_add_comment — 發布報告
2. complete_task

## 邊界
🚫 絕不：偽造健康狀態
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
    **kwargs: Any,
) -> dict[str, Any] | None:
    """Process an Infra Ops task."""
    agent = InfraOps(claude_client, linear_client, discord_notifier)
    result = await agent.run(task)
    return result
