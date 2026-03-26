"""Spec Architect agent — converts PRD into technical specifications."""

from __future__ import annotations

from typing import Any

import logging

from shared.agent_base import AgentTask, BaseAgent
from shared.claude_client import ClaudeClient
from shared.discord_notifier import DiscordNotifier
from shared.linear_client import LinearClient
from shared.models import AgentRole
from shared.tools import PLANNING_TOOLS

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
你是 📐 技術規格師，負責將 PRD 轉化為詳細的技術規格書。

## 你收到的輸入
產品策略師的 PRD（在 issue description 或 comments 中）。

## 你的任務
1. 讀取 issue 的 PRD 內容
2. 產出完整的技術規格書並發布為 Linear comment
3. 為每個實作單元建立 sub-issues
4. 呼叫 complete_task 完成任務

## 輸出格式（Linear Comment）
# 📐 技術規格書
## 1. 資料模型（含完整 SQL DDL，可直接執行）
## 2. API 合約（每個 endpoint 含 request/response JSON 範例）
## 3. UI 元件樹（含 props 定義和狀態管理）
## 4. 業務邏輯（驗證規則、邊界案例）
## 5. 驗收標準（AC-01, AC-02... 可測試的條件）

## 工具使用順序
1. linear_query_issues — 查詢相關 issue 和前一個 agent 的產出
2. linear_add_comment — 發布技術規格書
3. linear_create_issue — 為每個實作單元建立 sub-issue
4. complete_task — next_status: "Spec Complete"

## 品質標準
- SQL DDL 必須可直接在 PostgreSQL 執行
- API 範例必須包含完整的 request/response body
- 每個 AC 必須是可自動測試的條件

## 邊界
✅ 總是：引用 PRD 需求編號（R1, R2）、使用 code blocks
🚫 絕不：產出無法執行的偽代碼、跳過驗收標準
"""


class SpecArchitect(BaseAgent):
    role = AgentRole.SPEC_ARCHITECT
    system_prompt = SYSTEM_PROMPT
    tools = PLANNING_TOOLS


async def execute(
    task: AgentTask,
    claude_client: ClaudeClient,
    linear_client: LinearClient,
    discord_notifier: DiscordNotifier,
    **kwargs: Any,
) -> dict[str, Any] | None:
    """Process a Spec Architect task."""
    agent = SpecArchitect(claude_client, linear_client, discord_notifier)
    result = await agent.run(task)
    return result
