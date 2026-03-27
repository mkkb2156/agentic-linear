"""Discord message listener — routes messages to intent router or conversation store."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import discord

from shared.conversation_store import ConversationStore, Message

logger = logging.getLogger(__name__)


class ConversationListener:
    def __init__(
        self,
        conversation_store: ConversationStore,
        intent_router: Any,
        gatherer: Any,
        dispatcher: Any,
        linear_client: Any,
        bot_user_id: int,
        listen_channels: list[str],
    ) -> None:
        self._conversation_store = conversation_store
        self._intent_router = intent_router
        self._gatherer = gatherer
        self._dispatcher = dispatcher
        self._linear = linear_client
        self._bot_user_id = bot_user_id
        self._listen_channels = listen_channels

    def should_ignore(self, message: discord.Message) -> bool:
        if message.author.id == self._bot_user_id:
            return True
        if message.author.bot and not self.is_webhook_message(message):
            return True
        return False

    def is_mention(self, message: discord.Message) -> bool:
        return any(m.id == self._bot_user_id for m in message.mentions)

    def is_monitored_channel(self, message: discord.Message) -> bool:
        channel_name = getattr(message.channel, "name", "")
        return channel_name in self._listen_channels

    def is_webhook_message(self, message: discord.Message) -> bool:
        return message.webhook_id is not None

    def is_in_tracked_thread(self, message: discord.Message) -> bool:
        thread_id = str(message.channel.id)
        return self._conversation_store.get_thread(thread_id) is not None

    def is_dm(self, message: discord.Message) -> bool:
        return isinstance(message.channel, discord.DMChannel)

    async def handle_message(self, message: discord.Message) -> None:
        if self.should_ignore(message):
            return

        # Webhook messages (from agents) → store only
        if self.is_webhook_message(message):
            if self.is_in_tracked_thread(message):
                self._store_message(message, author_type="agent")
            return

        # Check if this replies to a pending agent question
        thread_id = str(message.channel.id)
        if self.is_in_tracked_thread(message):
            self._store_message(message, author_type="user")
            if self._conversation_store.has_pending(thread_id):
                self._conversation_store.resolve_any_pending(thread_id, message.content)
                return

        # DM → multi-turn gatherer
        if self.is_dm(message):
            await self._handle_dm(message)
            return

        # Monitored channel or @mention → intent router
        if self.is_monitored_channel(message) or self.is_mention(message):
            await self._handle_intent(message)
            return

    async def _handle_dm(self, message: discord.Message) -> None:
        user_id = str(message.author.id)
        dm = self._conversation_store.get_dm(user_id)

        if dm and dm.state == "gathering":
            result = await self._gatherer.continue_gathering(user_id, message.content)
            if result["type"] == "confirm":
                summary = await self._gatherer.build_summary(user_id)
                confirm_msg = self._format_confirmation(summary)
                await message.channel.send(confirm_msg)
            else:
                await message.channel.send(result["message"])
        elif dm and dm.state == "confirming":
            if message.content.strip().lower() in ("ok", "yes", "好", "開始", "確認", "y"):
                self._conversation_store.update_dm_state(user_id, "confirmed")
                await message.channel.send("✅ 開始啟動 Pipeline...")
                await self._create_project_from_dm(message)
            else:
                self._conversation_store.update_dm_state(user_id, "gathering")
                result = await self._gatherer.continue_gathering(user_id, message.content)
                await message.channel.send(result["message"])
        else:
            from services.gateway.discord.intent_router import IntentResult

            intent = await self._intent_router.classify(message.content, "DM")
            if intent.intent == "new_project":
                question = await self._gatherer.start_gathering(user_id, message.content)
                await message.channel.send(f"收到！讓我了解一下需求：\n\n{question}")
            elif intent.intent == "question":
                await self._handle_question(message, intent)
            else:
                await message.channel.send("你好！我可以幫你建立新專案或查詢進度。試試告訴我你想做什麼？")

    async def _handle_intent(self, message: discord.Message) -> None:
        channel_name = getattr(message.channel, "name", "unknown")
        intent = await self._intent_router.classify(message.content, channel_name)

        if intent.intent == "new_project":
            user_id = str(message.author.id)
            question = await self._gatherer.start_gathering(user_id, message.content)
            thread = await message.create_thread(name=f"需求收集: {message.content[:50]}")
            await thread.send(f"收到！讓我了解一下需求：\n\n{question}")

        elif intent.intent == "task_feedback" and intent.target_issue:
            await self._handle_feedback(message, intent)

        elif intent.intent == "question":
            await self._handle_question(message, intent)

        elif intent.intent == "agent_command" and intent.target_agent:
            await self._handle_agent_command(message, intent)

        elif intent.intent == "irrelevant":
            pass

    async def _handle_question(self, message: discord.Message, intent: Any) -> None:
        await message.reply(f"正在查詢... ({intent.summary})")

    async def _handle_feedback(self, message: discord.Message, intent: Any) -> None:
        await message.reply(f"收到回饋，正在更新 {intent.target_issue}...")

    async def _handle_agent_command(self, message: discord.Message, intent: Any) -> None:
        await message.reply(f"正在派遣 {intent.target_agent}...")

    async def _create_project_from_dm(self, message: discord.Message) -> None:
        user_id = str(message.author.id)
        summary = await self._gatherer.build_summary(user_id)
        logger.info("Creating project from DM: %s", summary)

    def _store_message(self, message: discord.Message, author_type: str = "user") -> None:
        thread_id = str(message.channel.id)
        try:
            self._conversation_store.append_message(
                thread_id,
                Message(
                    author_type=author_type,
                    author_id=str(message.author.id)
                    if author_type == "user"
                    else str(message.author.name),
                    content=message.content,
                    timestamp=datetime.now(timezone.utc),
                    reply_to=str(message.reference.message_id) if message.reference else None,
                ),
            )
        except KeyError:
            pass

    def _format_confirmation(self, summary: dict) -> str:
        name = summary.get("name", "Unknown")
        users = summary.get("users", "N/A")
        features = summary.get("features", [])
        stack = summary.get("stack", "N/A")
        constraints = summary.get("constraints", [])

        features_str = "\n".join(f"  - {f}" for f in features) if features else "  - N/A"
        constraints_str = "\n".join(f"  - {c}" for c in constraints) if constraints else "  - 無"

        return (
            f"**需求確認** ✅\n"
            f"```\n"
            f"專案：{name}\n"
            f"用戶：{users}\n"
            f"核心功能：\n{features_str}\n"
            f"Stack：{stack}\n"
            f"限制：\n{constraints_str}\n"
            f"```\n"
            f"確認要開始嗎？（回覆「開始」）"
        )
