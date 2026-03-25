from __future__ import annotations

import logging
from typing import Any

import httpx

from shared.models import AGENT_IDENTITIES, AgentRole

logger = logging.getLogger(__name__)


class DiscordNotifier:
    def __init__(self, webhook_urls: dict[str, str]) -> None:
        """
        webhook_urls keys: 'agent_hub', 'dashboard', 'alerts', 'deploy_log'
        """
        self._webhook_urls = webhook_urls
        self._client = httpx.AsyncClient(timeout=10.0)

    async def close(self) -> None:
        await self._client.aclose()

    async def notify(
        self,
        agent_role: AgentRole,
        channel: str,
        embed_data: dict[str, Any],
        thread_id: str | None = None,
    ) -> None:
        """Send a Discord webhook message with the agent's identity."""
        url = self._webhook_urls.get(channel)
        if not url:
            logger.warning("No webhook URL configured for channel: %s", channel)
            return

        identity = AGENT_IDENTITIES.get(agent_role, {})
        payload: dict[str, Any] = {
            "username": identity.get("name", str(agent_role)),
            "embeds": [self._build_embed(agent_role, embed_data)],
        }

        if thread_id:
            url = f"{url}?thread_id={thread_id}"

        try:
            resp = await self._client.post(url, json=payload)
            resp.raise_for_status()
            logger.info("Discord notification sent to %s by %s", channel, agent_role)
        except httpx.HTTPError as e:
            logger.error("Failed to send Discord notification: %s", e)

    def _build_embed(self, agent_role: AgentRole, data: dict[str, Any]) -> dict[str, Any]:
        """Build a Discord embed with agent identity styling."""
        identity = AGENT_IDENTITIES.get(agent_role, {})
        color_hex = identity.get("color", "#808080").lstrip("#")
        color_int = int(color_hex, 16)

        embed: dict[str, Any] = {
            "color": color_int,
            "author": {
                "name": identity.get("name", str(agent_role)),
            },
        }

        if "title" in data:
            embed["title"] = data["title"]
        if "description" in data:
            embed["description"] = data["description"]
        if "fields" in data:
            embed["fields"] = data["fields"]
        if "footer" in data:
            embed["footer"] = {"text": data["footer"]}

        return embed

    async def send_status_change(
        self,
        agent_role: AgentRole,
        issue_id: str,
        issue_title: str,
        old_status: str,
        new_status: str,
    ) -> None:
        """Send a status change notification."""
        await self.notify(
            agent_role=agent_role,
            channel="agent_hub",
            embed_data={
                "title": f"{issue_id}: {issue_title}",
                "description": f"**{old_status}** → **{new_status}**",
                "fields": [
                    {"name": "Issue", "value": issue_id, "inline": True},
                    {"name": "Agent", "value": str(agent_role), "inline": True},
                ],
            },
        )

    async def send_task_complete(
        self,
        agent_role: AgentRole,
        issue_id: str,
        summary: str,
    ) -> None:
        """Send a task completion notification."""
        await self.notify(
            agent_role=agent_role,
            channel="agent_hub",
            embed_data={
                "title": f"Task Complete: {issue_id}",
                "description": summary,
            },
        )

    async def send_alert(
        self,
        agent_role: AgentRole,
        title: str,
        description: str,
    ) -> None:
        """Send a critical alert."""
        await self.notify(
            agent_role=agent_role,
            channel="alerts",
            embed_data={
                "title": f"🚨 {title}",
                "description": description,
            },
        )
