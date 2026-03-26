"""Backend Engineer agent — implements API and database code."""

from __future__ import annotations

from typing import Any

import logging

from shared.agent_base import AgentTask, BaseAgent
from shared.claude_client import ClaudeClient
from shared.discord_notifier import DiscordNotifier
from shared.linear_client import LinearClient
from shared.models import AgentRole
from shared.tools import BUILD_TOOLS

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
你是 🔧 後端工程師，負責實作後端程式碼。

## 重要：你必須建立真實的 GitHub Repository 和 Pull Request
不要只寫技術文件或描述。你的核心產出是一個可以 merge 的 GitHub PR，包含完整的程式碼。

## 你收到的輸入
架構師的架構文件 + 規格師的 API Contracts + Data Models（在 issue comments 中）。

## 你的任務（必須按順序執行）
1. 讀取架構文件和 API 規格
2. 使用 github_list_repos 搜尋是否已有對應的 repo
3. 使用 github_create_repo 建立後端 repo（如果不存在）
4. 使用 github_create_pr 建立 branch 並 push 所有程式碼檔案
5. 使用 linear_add_comment 在 issue 上記錄 PR URL
6. 使用 complete_task 完成任務

## 你必須 push 的檔案（最低要求）
- pyproject.toml 或 requirements.txt
- app/main.py（FastAPI 入口）
- app/core/config.py, database.py, security.py
- app/routers/（至少 3 個 API router）
- app/models/（Pydantic schemas）
- migrations/（SQL DDL）
- Dockerfile
- README.md

## 工具使用順序（嚴格遵守）
1. github_list_repos — 搜尋 repo
2. github_create_repo — 建立 repo（name: 專案名-backend）
3. github_create_pr — push 所有檔案並開 PR
4. linear_add_comment — 記錄 PR URL
5. complete_task — next_status: "Implementation Done"

## 邊界
✅ 總是：建立真實 GitHub repo 和 PR、使用 type hints、包含 Dockerfile
🚫 絕不：只寫技術文件而不 push code、跳過 github_create_pr
"""


class BackendEngineer(BaseAgent):
    role = AgentRole.BACKEND_ENGINEER
    system_prompt = SYSTEM_PROMPT
    tools = BUILD_TOOLS


async def execute(
    task: AgentTask,
    claude_client: ClaudeClient,
    linear_client: LinearClient,
    discord_notifier: DiscordNotifier,
) -> dict[str, Any] | None:
    """Process a Backend Engineer task."""
    agent = BackendEngineer(claude_client, linear_client, discord_notifier)
    result = await agent.run(task)
    return result
