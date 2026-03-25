from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands


def setup_commands(bot: commands.Bot) -> None:
    """Register slash commands on the bot's command tree."""

    @bot.tree.command(name="agent", description="查看 Agent 狀態")
    @app_commands.describe(name="Agent name (optional)")
    async def agent_status(interaction: discord.Interaction, name: str | None = None) -> None:
        if name:
            await interaction.response.send_message(
                f"Agent `{name}` status — coming in Phase 2", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "All agents status — coming in Phase 2", ephemeral=True
            )

    @bot.tree.command(name="pipeline", description="查看 Pipeline 狀態")
    async def pipeline_view(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            "Pipeline view — coming in Phase 2", ephemeral=True
        )

    @bot.tree.command(name="task", description="任務操作")
    @app_commands.describe(action="create / assign", value="Task details")
    async def task_cmd(interaction: discord.Interaction, action: str, value: str) -> None:
        await interaction.response.send_message(
            f"Task `{action}`: {value} — coming in Phase 2", ephemeral=True
        )
