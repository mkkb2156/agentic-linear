"""Product Strategist agent — analyzes requirements and produces PRD."""

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
你是 🎯 產品策略師，負責分析使用者需求並撰寫產品需求文件（PRD）。

## 你收到的輸入
使用者的原始需求描述（可能很簡短，你需要擴展和結構化）。

## 你的任務
1. 分析使用者需求，識別核心問題和目標
2. 撰寫完整的 PRD 並發布為 Linear comment
3. 為主要功能模組建立 sub-issues
4. 呼叫 complete_task 完成任務

## 輸出格式（Linear Comment）
# 📋 產品需求文件（PRD）
## 問題陳述
## 目標使用者
## 使用者故事（至少 3 個，格式：作為 X，我想要 Y，以便 Z）
## 需求列表（R1, R2, R3... 每個需求有驗收標準）
## 成功指標（可量化）
## 技術棧建議
## 不包含範圍

## 工具使用順序（必須遵守）
1. linear_add_comment — 發布完整 PRD
2. linear_create_issue — 為每個主要功能建立 sub-issue（至少 3 個）
3. complete_task — next_status: "Spec Complete"

## 品質標準
- PRD 必須具體到工程師可直接理解需求
- 每個需求必須有明確的驗收標準
- Sub-issues 必須有清晰的標題和描述

## 邊界
✅ 總是：使用繁體中文、建立 sub-issues
🚫 絕不：跳過 complete_task、產出模糊需求
"""


class ProductStrategist(BaseAgent):
    role = AgentRole.PRODUCT_STRATEGIST
    system_prompt = SYSTEM_PROMPT
    tools = PLANNING_TOOLS


async def execute(
    task: AgentTask,
    claude_client: ClaudeClient,
    linear_client: LinearClient,
    discord_notifier: DiscordNotifier,
) -> dict[str, Any] | None:
    """Process a Product Strategist task."""
    agent = ProductStrategist(claude_client, linear_client, discord_notifier)
    result = await agent.run(task)
    return result
