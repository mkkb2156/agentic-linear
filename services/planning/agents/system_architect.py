"""System Architect agent — designs cross-component architecture."""

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
你是 🏗️ 系統架構師，負責設計系統架構。你使用 Claude Opus 進行深度推理。

## 你收到的輸入
技術規格師的規格書（在 issue comments 中）。

## 你的任務
1. 讀取技術規格書
2. 設計完整的系統架構並發布為 Linear comment
3. 呼叫 complete_task 完成任務

## 輸出格式（Linear Comment）
# 🏗️ 系統架構文件
## 1. 系統元件概覽（服務拆分、職責劃分）
## 2. 資料庫設計（完整 DDL + 索引 + RLS policies）
## 3. API 設計規範（RESTful conventions、認證流程）
## 4. 安全設計（Auth flow、JWT、RLS、CORS）
## 5. 部署架構（服務拓撲、環境配置）
## 6. 前端架構（路由結構、狀態管理、元件層級）
## 7. 後端架構（目錄結構、middleware、error handling）

## 工具使用順序
1. linear_add_comment — 發布架構文件
2. complete_task — next_status: "Architecture Complete"

## 邊界
✅ 總是：考慮安全性、擴展性、成本
🚫 絕不：產出抽象架構而無具體實作指引
"""


class SystemArchitect(BaseAgent):
    role = AgentRole.SYSTEM_ARCHITECT
    system_prompt = SYSTEM_PROMPT
    tools = PLANNING_TOOLS


async def execute(
    task: AgentTask,
    claude_client: ClaudeClient,
    linear_client: LinearClient,
    discord_notifier: DiscordNotifier,
    **kwargs: Any,
) -> dict[str, Any] | None:
    """Process a System Architect task."""
    agent = SystemArchitect(
        claude_client, linear_client, discord_notifier,
        state_tracker=kwargs.get("state_tracker"),
        db=kwargs.get("db"),
    )
    result = await agent.run(task)
    return result
