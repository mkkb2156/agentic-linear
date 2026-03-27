from __future__ import annotations

import asyncio
import logging
from typing import Any

import discord
from discord.ext import commands

from .commands import setup_commands

logger = logging.getLogger(__name__)

_bot: commands.Bot | None = None
_bot_task: asyncio.Task[None] | None = None


def create_bot(
    *,
    linear_client: Any = None,
    claude_client: Any = None,
    discord_notifier: Any = None,
    dispatcher: Any = None,
    github_client: Any = None,
    metrics_store: Any = None,
    config_manager: Any = None,
    conversation_store: Any = None,
    intent_router: Any = None,
    gatherer: Any = None,
) -> commands.Bot:
    intents = discord.Intents.default()
    intents.guilds = True
    intents.messages = True
    intents.message_content = True  # Privileged intent — enable in Discord Developer Portal

    bot = commands.Bot(command_prefix="!", intents=intents)

    # Store client references on the bot instance for commands to use
    bot.linear_client = linear_client  # type: ignore[attr-defined]
    bot.claude_client = claude_client  # type: ignore[attr-defined]
    bot.discord_notifier = discord_notifier  # type: ignore[attr-defined]
    bot.dispatcher = dispatcher  # type: ignore[attr-defined]
    bot.github_client = github_client  # type: ignore[attr-defined]
    bot.metrics_store = metrics_store  # type: ignore[attr-defined]
    bot.config_manager = config_manager  # type: ignore[attr-defined]
    bot.conversation_store = conversation_store  # type: ignore[attr-defined]

    _listener = None

    @bot.event
    async def on_ready() -> None:
        nonlocal _listener
        logger.info("Discord bot connected as %s", bot.user)

        if conversation_store and intent_router and gatherer:
            from shared.config import get_settings
            settings = get_settings()
            from .listener import ConversationListener
            _listener = ConversationListener(
                conversation_store=conversation_store,
                intent_router=intent_router,
                gatherer=gatherer,
                dispatcher=dispatcher,
                linear_client=linear_client,
                bot_user_id=bot.user.id,
                listen_channels=settings.listen_channels.split(","),
            )
            logger.info("ConversationListener initialized (channels: %s)", settings.listen_channels)

        try:
            synced = await bot.tree.sync()
            logger.info("Synced %d slash commands", len(synced))
        except Exception as e:
            logger.error("Failed to sync commands: %s", e)

    @bot.event
    async def on_message(message: discord.Message) -> None:
        if _listener:
            await _listener.handle_message(message)
        await bot.process_commands(message)

    setup_commands(bot)
    return bot


async def start_bot(
    token: str,
    *,
    linear_client: Any = None,
    claude_client: Any = None,
    discord_notifier: Any = None,
    dispatcher: Any = None,
    github_client: Any = None,
    metrics_store: Any = None,
    config_manager: Any = None,
    conversation_store: Any = None,
    intent_router: Any = None,
    gatherer: Any = None,
) -> None:
    global _bot, _bot_task
    _bot = create_bot(
        linear_client=linear_client,
        claude_client=claude_client,
        discord_notifier=discord_notifier,
        dispatcher=dispatcher,
        github_client=github_client,
        metrics_store=metrics_store,
        config_manager=config_manager,
        conversation_store=conversation_store,
        intent_router=intent_router,
        gatherer=gatherer,
    )
    _bot_task = asyncio.create_task(_bot.start(token))
    logger.info("Discord bot starting...")


async def stop_bot() -> None:
    global _bot, _bot_task
    if _bot:
        await _bot.close()
        _bot = None
    if _bot_task:
        _bot_task.cancel()
        _bot_task = None
    logger.info("Discord bot stopped")
