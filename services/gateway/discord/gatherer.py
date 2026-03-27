"""Multi-turn requirement gathering for new projects via DM or channel."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import anthropic

from shared.conversation_store import ConversationStore, Message

logger = logging.getLogger(__name__)

HAIKU_MODEL = "claude-haiku-4-5-20251001"

GATHER_SYSTEM = """你是專案需求收集助手。用戶想建立一個新專案，你需要逐步收集以下資訊：

必填：
- 專案名稱
- 目標用戶
- 核心功能（至少 1-3 個）
- 技術 stack 偏好

選填：
- 平台限制（尺寸、格式等）
- 時程
- 第三方整合

規則：
- 每次只問一個問題
- 用繁體中文
- 簡潔友善
- 如果用戶已經在訊息中提供了資訊，不要重複問

根據目前對話，判斷還缺什麼資訊，然後問下一個問題。
如果資訊已經足夠，回覆 "READY" 開頭，後面接 JSON 摘要。"""

SUMMARY_SYSTEM = """根據對話內容，整理出專案需求摘要。回傳 JSON：
{
  "name": "專案名稱",
  "users": "目標用戶",
  "features": ["功能1", "功能2"],
  "stack": "技術 stack",
  "constraints": ["限制1"],
  "extras": "其他備註"
}"""


class MultiTurnGatherer:
    def __init__(
        self,
        api_key: str,
        conversation_store: ConversationStore,
    ) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._conversation_store = conversation_store

    async def close(self) -> None:
        await self._client.close()

    async def _ask_haiku(self, system: str, messages_text: str) -> str:
        response = await self._client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=512,
            system=system,
            messages=[{"role": "user", "content": messages_text}],
        )
        return response.content[0].text.strip()

    async def start_gathering(self, user_id: str, initial_message: str) -> str:
        dm = self._conversation_store.get_dm(user_id)
        if not dm:
            self._conversation_store.create_dm(user_id)

        self._conversation_store.update_dm_state(user_id, "gathering")
        self._conversation_store.append_dm_message(user_id, Message(
            author_type="user",
            author_id=user_id,
            content=initial_message,
            timestamp=datetime.now(timezone.utc),
        ))

        question = await self._ask_haiku(
            GATHER_SYSTEM,
            f"用戶說：{initial_message}\n\n請問第一個問題：",
        )
        return question

    async def continue_gathering(self, user_id: str, user_reply: str) -> dict[str, Any]:
        dm = self._conversation_store.get_dm(user_id)
        if not dm:
            return {"type": "error", "message": "No active gathering session"}

        self._conversation_store.append_dm_message(user_id, Message(
            author_type="user",
            author_id=user_id,
            content=user_reply,
            timestamp=datetime.now(timezone.utc),
        ))

        history = "\n".join(
            f"{'用戶' if m.author_type == 'user' else 'Bot'}: {m.content}"
            for m in dm.messages
        )

        response_text = await self._ask_haiku(GATHER_SYSTEM, history)

        if response_text.startswith("READY"):
            self._conversation_store.update_dm_state(user_id, "confirming")
            return {"type": "confirm", "message": response_text}
        else:
            return {"type": "question", "message": response_text}

    async def build_summary(self, user_id: str) -> dict[str, Any]:
        dm = self._conversation_store.get_dm(user_id)
        if not dm:
            return {}

        history = "\n".join(
            f"{'用戶' if m.author_type == 'user' else 'Bot'}: {m.content}"
            for m in dm.messages
        )

        text = await self._ask_haiku(SUMMARY_SYSTEM, history)
        try:
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            return json.loads(text)
        except json.JSONDecodeError:
            return {"raw": text}
