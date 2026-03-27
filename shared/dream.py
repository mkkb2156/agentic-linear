"""Auto-Dream — memory consolidation using direct Anthropic SDK calls.

Periodically cleans up agent souls and project contexts:
  - Deletes outdated info (fixed bugs, deleted files)
  - Merges duplicate entries
  - Converts relative dates to absolute dates
  - Resolves contradictions (keep latest)
  - Enforces line limits (100 for souls, 150 for projects)
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date

import anthropic

from shared.project_context import ProjectContextManager
from shared.soul_manager import SoulManager

logger = logging.getLogger(__name__)

SOUL_LINE_LIMIT = 100
PROJECT_LINE_LIMIT = 150
DREAM_MODEL = "claude-sonnet-4-6"

CONSOLIDATION_SYSTEM = (
    "你是記憶整理器。整理以下記憶檔案：\n"
    "1. 刪除過時資訊（已修復的 bug、已刪除的檔案）\n"
    "2. 合併重複條目\n"
    "3. 相對日期 → 絕對日期\n"
    "4. 矛盾經驗保留最新\n"
    "5. 控制在 {line_limit} 行以內\n"
    "6. 保持 markdown 格式，保留 section headers\n"
    "輸出整理後的完整檔案內容，不要其他說明。"
)


class DreamConsolidator:
    def __init__(
        self,
        api_key: str,
        soul_manager: SoulManager,
        project_context_manager: ProjectContextManager,
        learnings_reader: Callable[..., str] | None = None,
    ) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._soul = soul_manager
        self._project_ctx = project_context_manager
        self._read_learnings = learnings_reader or (lambda **_: "")

    async def close(self) -> None:
        await self._client.close()

    async def _call_claude(self, system: str, user_content: str) -> anthropic.types.Message:
        return await self._client.messages.create(
            model=DREAM_MODEL,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user_content}],
        )

    async def dream_soul(self, role: str) -> None:
        current = self._soul.load(role)
        if not current:
            logger.info("Dream skipped for %s: no existing soul", role)
            return

        learnings = self._read_learnings(role=role)
        system = CONSOLIDATION_SYSTEM.format(line_limit=SOUL_LINE_LIMIT)
        user_content = (
            f"現有記憶:\n{current}\n\n"
            f"近期學習紀錄:\n{learnings}\n\n"
            f"今天日期: {date.today().isoformat()}"
        )

        try:
            response = await self._call_claude(system, user_content)
            consolidated = response.content[0].text
            self._soul.write(role, consolidated)
            logger.info("Dream completed for soul: %s", role)
        except Exception as e:
            logger.error("Dream failed for soul %s: %s", role, e)

    async def dream_project(self, project_id: str) -> None:
        current = self._project_ctx.load(project_id)
        if not current:
            logger.info("Dream skipped for project %s: no existing context", project_id)
            return

        learnings = self._read_learnings()
        system = CONSOLIDATION_SYSTEM.format(line_limit=PROJECT_LINE_LIMIT)
        user_content = (
            f"現有專案記憶:\n{current}\n\n"
            f"近期學習紀錄:\n{learnings}\n\n"
            f"今天日期: {date.today().isoformat()}"
        )

        try:
            response = await self._call_claude(system, user_content)
            consolidated = response.content[0].text
            self._project_ctx.write(project_id, consolidated)
            logger.info("Dream completed for project: %s", project_id)
        except Exception as e:
            logger.error("Dream failed for project %s: %s", project_id, e)
