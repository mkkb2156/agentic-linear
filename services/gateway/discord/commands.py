from __future__ import annotations

import logging
import uuid

import discord
from discord import app_commands
from discord.ext import commands

from shared.agent_base import AgentTask
from shared.models import AgentRole

logger = logging.getLogger(__name__)

DRONE168_TEAM_ID = "58f0da33-5510-46b1-a9fb-55b8de6a27cd"


def setup_commands(bot: commands.Bot) -> None:
    """Register slash commands on the bot's command tree."""

    @bot.tree.command(name="project", description="建立新專案並觸發 Pipeline")
    @app_commands.describe(description="專案描述 (PRD)")
    async def project_create(interaction: discord.Interaction, description: str) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        linear = bot.linear_client  # type: ignore[attr-defined]

        try:
            # Extract project name: use first line, strip to 80 chars, no newlines
            lines = description.strip().split("\n")
            project_name = lines[0][:80].strip()

            # Create a Linear project
            project_result = await linear._graphql(
                """
                mutation CreateProject($input: ProjectCreateInput!) {
                    projectCreate(input: $input) {
                        success
                        project { id name }
                    }
                }
                """,
                {
                    "input": {
                        "name": project_name,
                        "teamIds": [DRONE168_TEAM_ID],
                    }
                },
            )
            project = project_result.get("projectCreate", {}).get("project", {})
            project_id = project.get("id", "")

            # Create an issue with the description as PRD
            kwargs: dict = {"description": description}
            if project_id:
                kwargs["projectId"] = project_id

            issue_result = await linear.create_issue(
                team_id=DRONE168_TEAM_ID,
                title=project_name,
                **kwargs,
            )
            issue = issue_result.get("issue", {})
            issue_id = issue.get("id", "")
            identifier = issue.get("identifier", "")

            # Set status to "Strategy Complete" to trigger pipeline
            if issue_id:
                await linear.transition_issue(issue_id, "Strategy Complete")

            issue_url = f"https://linear.app/drone168/issue/{identifier}"
            await interaction.followup.send(
                f"已建立專案與 Issue [{identifier}]({issue_url})，Pipeline 已啟動。",
                ephemeral=True,
            )
        except Exception as e:
            logger.exception("Failed to create project: %s", e)
            await interaction.followup.send(f"建立失敗: {e}", ephemeral=True)

    @bot.tree.command(name="run", description="觸發現有 Issue 的 Pipeline")
    @app_commands.describe(
        issue_id="Linear Issue ID (UUID)",
        status="目標狀態 (預設: Strategy Complete)",
    )
    async def run_pipeline(
        interaction: discord.Interaction,
        issue_id: str,
        status: str = "Strategy Complete",
    ) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        linear = bot.linear_client  # type: ignore[attr-defined]

        try:
            result = await linear.transition_issue(issue_id, status)
            success = result.get("success", False)
            if success:
                await interaction.followup.send(
                    f"已將 Issue `{issue_id}` 狀態設為 **{status}**，Pipeline 已觸發。",
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    f"狀態轉換失敗，請確認 Issue ID 與狀態名稱是否正確。",
                    ephemeral=True,
                )
        except Exception as e:
            logger.exception("Failed to run pipeline: %s", e)
            await interaction.followup.send(f"執行失敗: {e}", ephemeral=True)

    @bot.tree.command(name="status", description="查看 Pipeline 狀態")
    @app_commands.describe(issue_id="Linear Issue ID (可選)")
    async def status_check(
        interaction: discord.Interaction, issue_id: str | None = None
    ) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            if issue_id:
                linear = bot.linear_client  # type: ignore[attr-defined]
                issue = await linear.get_issue(issue_id)
                state_name = issue.get("state", {}).get("name", "Unknown")
                title = issue.get("title", "N/A")
                identifier = issue.get("identifier", issue_id)

                dispatcher = bot.dispatcher  # type: ignore[attr-defined]
                active = dispatcher.active_count

                embed = discord.Embed(
                    title=f"Issue {identifier}",
                    description=title,
                    color=0x4ECDC4,
                )
                embed.add_field(name="狀態", value=state_name, inline=True)
                embed.add_field(name="活躍 Agents", value=str(active), inline=True)
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                dispatcher = bot.dispatcher  # type: ignore[attr-defined]
                registered = len(dispatcher._registry)
                active = dispatcher.active_count

                embed = discord.Embed(
                    title="Pipeline 健康狀態",
                    color=0x00E676,
                )
                embed.add_field(name="已註冊 Agents", value=str(registered), inline=True)
                embed.add_field(name="活躍 Agents", value=str(active), inline=True)
                await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.exception("Failed to check status: %s", e)
            await interaction.followup.send(f"查詢失敗: {e}", ephemeral=True)

    @bot.tree.command(name="admin", description="管理平台 — 報告/配置/學習分析")
    @app_commands.describe(
        action="操作類型: report / config / learn",
        detail="補充細節 (可選)",
    )
    async def admin_command(
        interaction: discord.Interaction,
        action: str,
        detail: str | None = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            prompt_map = {
                "report": "產出本週 Agent 績效報告（含各 agent 成功率、token 消耗、平均執行時間），發布到 Discord #dashboard。",
                "config": "列出所有 agent 的當前配置，包含模型、技能、最大輪次、啟用狀態。",
                "learn": "檢視學習紀錄和 metrics，分析模式和優化機會，必要時更新 skill 文件。將分析報告發布到 Discord #dashboard。",
            }
            prompt = prompt_map.get(action)
            if not prompt:
                await interaction.followup.send(
                    f"未知的操作: `{action}`\n可用: report, config, learn",
                    ephemeral=True,
                )
                return

            if detail:
                prompt += f"\n補充: {detail}"

            task = AgentTask(
                issue_id=f"admin-{uuid.uuid4().hex[:8]}",
                agent_role="admin",
                payload={
                    "prompt": prompt,
                    "_metrics_store": getattr(bot, "metrics_store", None),
                    "_config_manager": getattr(bot, "config_manager", None),
                },
            )

            dispatcher = bot.dispatcher  # type: ignore[attr-defined]
            dispatched = await dispatcher.dispatch(AgentRole.ADMIN, task)

            if dispatched:
                await interaction.followup.send(
                    f"已派遣管理官處理 `{action}` 請求。結果將發布至 Discord。",
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    "無法派遣管理官，可能未註冊或重複請求。",
                    ephemeral=True,
                )
        except Exception as e:
            logger.exception("Failed to dispatch admin: %s", e)
            await interaction.followup.send(f"管理操作失敗: {e}", ephemeral=True)

    @bot.tree.command(name="agent", description="直接對特定 Agent 發送提示")
    @app_commands.describe(agent_name="Agent 名稱", prompt="提示內容")
    async def agent_prompt(
        interaction: discord.Interaction, agent_name: str, prompt: str
    ) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            # Validate agent name
            try:
                role = AgentRole(agent_name)
            except ValueError:
                valid = ", ".join(r.value for r in AgentRole)
                await interaction.followup.send(
                    f"未知的 Agent: `{agent_name}`\n可用: {valid}",
                    ephemeral=True,
                )
                return

            # Create a temporary AgentTask
            task = AgentTask(
                issue_id=f"discord-{uuid.uuid4().hex[:8]}",
                agent_role=agent_name,
                payload={
                    "event": {"data": {}},
                    "old_status": "Manual",
                    "new_status": "Manual",
                    "prompt": prompt,
                },
            )

            dispatcher = bot.dispatcher  # type: ignore[attr-defined]
            dispatched = await dispatcher.dispatch(role, task)

            if dispatched:
                await interaction.followup.send(
                    f"已派遣 `{agent_name}` 處理你的請求。結果將發布至 Discord。",
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    f"無法派遣 `{agent_name}`，可能未註冊或重複請求。",
                    ephemeral=True,
                )
        except Exception as e:
            logger.exception("Failed to dispatch agent: %s", e)
            await interaction.followup.send(f"派遣失敗: {e}", ephemeral=True)
