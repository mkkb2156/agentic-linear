from __future__ import annotations

import asyncio
import logging

import discord
from discord.ext import commands

from .commands import setup_commands

logger = logging.getLogger(__name__)

_bot: commands.Bot | None = None
_bot_task: asyncio.Task[None] | None = None


def create_bot() -> commands.Bot:
    intents = discord.Intents.default()
    intents.guilds = True
    intents.messages = True

    bot = commands.Bot(command_prefix="!", intents=intents)

    @bot.event
    async def on_ready() -> None:
        logger.info("Discord bot connected as %s", bot.user)
        # Sync slash commands
        try:
            synced = await bot.tree.sync()
            logger.info("Synced %d slash commands", len(synced))
        except Exception as e:
            logger.error("Failed to sync commands: %s", e)

    setup_commands(bot)
    return bot


async def start_bot(token: str) -> None:
    global _bot, _bot_task
    _bot = create_bot()
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
