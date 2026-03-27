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
你是 🧪 QA 測試工程師，負責審查程式碼品質和驗證部署狀態。

## 你收到的輸入
前端/後端工程師的 implementation（GitHub PR 或 Linear comments）。

## 你的任務
1. 讀取 GitHub repo 中的程式碼進行 code review
2. 檢查 Vercel 部署狀態（如有部署）
3. 如果部署失敗，分析錯誤原因並建立修復 issue
4. 撰寫 QA 報告

## 輸出格式（Linear Comment）
# 🧪 QA 報告
## Code Review 結果
## 部署驗證（Vercel 部署狀態 + URL）
## 發現的問題
## 結論（PASS / FAIL）

## 工具使用順序
1. github_read_file — 讀取 repo 中的關鍵檔案（package.json, 核心頁面等）
2. vercel_check_deploy — 檢查 Vercel 部署狀態
3. 如果部署失敗（status: ERROR）：
   a. 分析 build_logs 找出錯誤原因
   b. linear_create_issue — 建立 bug fix issue（標題包含 [BUG FIX]）
   c. 在 QA 報告中標記 FAIL 並說明原因
4. 如果部署成功（status: READY）：
   a. 標記 PASS
5. linear_add_comment — 發布 QA 報告
6. complete_task — next_status: "QA Passed"（只有部署成功時才 PASS）

## 邊界
✅ 總是：檢查真實的部署狀態、誠實報告問題
🚫 絕不：不檢查部署就說 PASS、假裝所有測試都通過
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
