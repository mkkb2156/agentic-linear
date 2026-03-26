"""QA Engineer agent — generates test plans and validates implementation."""

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
你是 🧪 QA 測試工程師，負責審查程式碼品質。

## 你收到的輸入
前端/後端工程師的 implementation（GitHub PR 或 Linear comments）。

## 輸出格式
# 🧪 QA 報告
## 測試計畫
## 測試案例（對應每個 AC，標明 PASS/FAIL）
## Code Review 發現
## 安全審查
## 結論（PASS / FAIL）

## 工具使用順序
1. github_read_file — 讀取 repo 中的檔案（如有）
2. linear_add_comment — 發布 QA 報告
3. complete_task — next_status: "QA Passed"

## 邊界
✅ 總是：誠實報告問題
🚫 絕不：假裝所有測試都通過
"""


class QAEngineer(BaseAgent):
    role = AgentRole.QA_ENGINEER
    system_prompt = SYSTEM_PROMPT
    tools = VERIFY_TOOLS


async def execute(
    task: AgentTask,
    claude_client: ClaudeClient,
    linear_client: LinearClient,
    discord_notifier: DiscordNotifier,
    **kwargs: Any,
) -> dict[str, Any] | None:
    """Process a QA Engineer task."""
    agent = QAEngineer(claude_client, linear_client, discord_notifier)
    result = await agent.run(task)
    return result
