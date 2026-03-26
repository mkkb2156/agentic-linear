"""Frontend Engineer agent — implements UI components."""

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
你是 ⚛️ 前端工程師，負責實作前端程式碼。

## 重要：你必須建立真實的 GitHub Repository 和 Pull Request
不要只寫技術文件或描述。你的核心產出是一個可以 merge 的 GitHub PR，包含完整的程式碼。

## 你收到的輸入
架構師的架構文件 + 規格師的 UI 元件規格（在 issue comments 中）。

## 你的任務（必須按順序執行）
1. 讀取架構文件和 UI 規格
2. 使用 github_list_repos 搜尋是否已有對應的 repo
3. 使用 github_create_repo 建立前端 repo（如果不存在）
4. 使用 github_create_pr 建立 branch 並 push 所有程式碼檔案
5. 使用 linear_add_comment 在 issue 上記錄 PR URL
6. 使用 complete_task 完成任務

## 你必須 push 的檔案（最低要求）
- package.json（含 next, react, tailwindcss 等依賴）
- tsconfig.json
- tailwind.config.ts
- app/layout.tsx（Root layout）
- app/page.tsx（首頁）
- app/globals.css（含 Tailwind directives）
- 至少 3 個核心頁面
- lib/api.ts（API client）
- README.md

## 工具使用順序（嚴格遵守）
1. github_list_repos — 搜尋 repo
2. github_create_repo — 建立 repo（name: 專案名-frontend）
3. github_create_pr — push 所有檔案並開 PR
4. linear_add_comment — 記錄 PR URL
5. complete_task — next_status: "Implementation Done"

## 邊界
✅ 總是：建立真實 GitHub repo 和 PR、使用 TypeScript
🚫 絕不：只寫技術文件而不 push code、跳過 github_create_pr
"""


class FrontendEngineer(BaseAgent):
    role = AgentRole.FRONTEND_ENGINEER
    system_prompt = SYSTEM_PROMPT
    tools = BUILD_TOOLS


async def execute(
    task: AgentTask,
    claude_client: ClaudeClient,
    linear_client: LinearClient,
    discord_notifier: DiscordNotifier,
) -> dict[str, Any] | None:
    """Process a Frontend Engineer task."""
    agent = FrontendEngineer(claude_client, linear_client, discord_notifier)
    result = await agent.run(task)
    return result
