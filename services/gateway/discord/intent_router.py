"""Intent classification using Claude Haiku for fast, cheap routing."""

from __future__ import annotations

import json
import logging
from typing import Literal

import anthropic
from pydantic import BaseModel

logger = logging.getLogger(__name__)

HAIKU_MODEL = "claude-haiku-4-5-20251001"

CLASSIFY_SYSTEM = """你是 Discord 訊息意圖分類器。根據訊息內容和頻道上下文，判斷用戶意圖。

回傳 JSON（不要 markdown code block）：
{
  "intent": "new_project" | "task_feedback" | "question" | "agent_command" | "conversation" | "irrelevant",
  "confidence": 0.0-1.0,
  "target_agent": null 或 agent role name（如 "frontend_engineer"）,
  "target_issue": null 或 issue identifier（如 "DRO-42"）,
  "summary": "一句話描述意圖"
}

意圖判斷規則：
- new_project: 「我想開發...」「建一個...」「新專案」「做一個...」
- task_feedback: 「改成...」「不對」「加功能」「需求變更」，通常提到特定 issue
- question: 「進度？」「測完了嗎？」「狀態如何」
- agent_command: 明確指定 agent 執行動作，如「叫 Frontend 重新部署」
- conversation: 在進行中的對話中回覆（通常在 thread 裡）
- irrelevant: 閒聊、與工作無關"""


class IntentResult(BaseModel):
    intent: Literal[
        "new_project", "task_feedback", "question",
        "agent_command", "conversation", "irrelevant"
    ]
    confidence: float = 0.0
    target_agent: str | None = None
    target_issue: str | None = None
    summary: str = ""


class IntentRouter:
    def __init__(self, api_key: str) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def close(self) -> None:
        await self._client.close()

    async def classify(self, message_content: str, channel_context: str) -> IntentResult:
        try:
            response = await self._client.messages.create(
                model=HAIKU_MODEL,
                max_tokens=256,
                system=CLASSIFY_SYSTEM,
                messages=[{
                    "role": "user",
                    "content": f"頻道: {channel_context}\n訊息: {message_content}",
                }],
            )
            text = response.content[0].text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            data = json.loads(text)
            return IntentResult(**data)
        except Exception as e:
            logger.error("Intent classification failed: %s", e)
            return IntentResult(intent="irrelevant", confidence=0.0, summary=f"Error: {e}")
