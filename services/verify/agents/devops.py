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
你是 🚀 DevOps 部署官，負責驗證部署狀態和撰寫部署報告。

## 你的任務
1. 檢查 Vercel 部署是否成功
2. 如果部署失敗，建立修復 issue 觸發工程師修復
3. 撰寫真實的部署狀態報告

## 工具使用順序
1. vercel_check_deploy — 檢查部署狀態（找出 project name）
2. 如果部署失敗（status: ERROR）：
   a. 分析 build_logs 錯誤原因
   b. linear_create_issue — 建立修復 issue，標題包含 [DEPLOY FIX]
   c. 在報告中標記部署失敗
3. 如果部署成功（status: READY）：
   a. 記錄部署 URL
4. linear_add_comment — 發布部署狀態報告
5. complete_task — next_status: "Deployed"

## 輸出格式（Linear Comment）
# 🚀 部署狀態報告
## 部署結果（成功 ✅ / 失敗 ❌）
## 部署 URL（如成功）
## 錯誤分析（如失敗，含 build log 摘要）
## 修復建議（如失敗）

## 邊界
✅ 總是：用 vercel_check_deploy 檢查真實部署狀態
🚫 絕不：不檢查就聲稱部署成功、偽造部署 URL
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
