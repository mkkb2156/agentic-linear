from __future__ import annotations

import logging
from datetime import datetime, timezone
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
        thread_name: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Send a Discord webhook message with the agent's identity.
        If thread_name is provided (and no thread_id), creates a new forum/thread.
        Returns the Discord message data (including thread info) or None on failure.
        """
        url = self._webhook_urls.get(channel)
        if not url:
            logger.warning("No webhook URL configured for channel: %s", channel)
            return None

        identity = AGENT_IDENTITIES.get(agent_role, {})
        payload: dict[str, Any] = {
            "username": identity.get("name", str(agent_role)),
            "avatar_url": identity.get("avatar_url", ""),
            "embeds": [self._build_embed(agent_role, embed_data)],
        }

        params: dict[str, str] = {}
        if thread_id:
            params["thread_id"] = thread_id
        if thread_name:
            payload["thread_name"] = thread_name

        try:
            request_url = f"{url}?wait=true"
            if params:
                param_str = "&".join(f"{k}={v}" for k, v in params.items())
                request_url += f"&{param_str}"

            resp = await self._client.post(request_url, json=payload)
            resp.raise_for_status()
            logger.info("Discord notification sent to %s by %s", channel, agent_role)
            return resp.json()
        except httpx.HTTPError as e:
            logger.error("Failed to send Discord notification: %s", e)
            return None

    def _build_embed(self, agent_role: AgentRole, data: dict[str, Any]) -> dict[str, Any]:
        """Build a Discord embed with agent identity styling."""
        identity = AGENT_IDENTITIES.get(agent_role, {})
        color_hex = identity.get("color", "#808080").lstrip("#")
        color_int = int(color_hex, 16)

        author: dict[str, str] = {
            "name": identity.get("name", str(agent_role)),
        }
        if identity.get("avatar_url"):
            author["icon_url"] = identity["avatar_url"]

        embed: dict[str, Any] = {
            "color": color_int,
            "author": author,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if "title" in data:
            embed["title"] = data["title"]
        if "description" in data:
            embed["description"] = data["description"][:4096]  # Discord limit
        if "fields" in data:
            embed["fields"] = data["fields"][:25]  # Discord limit
        if "footer" in data:
            embed["footer"] = {"text": data["footer"]}
        if "url" in data:
            embed["url"] = data["url"]

        return embed

    async def send_status_change(
        self,
        agent_role: AgentRole,
        issue_id: str,
        issue_title: str,
        old_status: str,
        new_status: str,
        thread_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Send a status change notification."""
        identity = AGENT_IDENTITIES.get(agent_role, {})
        emoji = identity.get("emoji", "🔄")

        return await self.notify(
            agent_role=agent_role,
            channel="agent_hub",
            embed_data={
                "title": f"{emoji} {issue_id}: {issue_title}",
                "description": f"**{old_status}** → **{new_status}**",
                "fields": [
                    {"name": "Issue", "value": issue_id, "inline": True},
                    {"name": "Agent", "value": identity.get("name", str(agent_role)), "inline": True},
                    {"name": "Status", "value": new_status, "inline": True},
                ],
            },
            thread_id=thread_id,
            thread_name=f"{issue_id}: {issue_title}" if not thread_id else None,
        )

    async def send_task_complete(
        self,
        agent_role: AgentRole,
        issue_id: str,
        summary: str,
        tokens_used: int = 0,
        model_used: str = "",
        thread_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Send a task completion notification."""
        identity = AGENT_IDENTITIES.get(agent_role, {})
        fields: list[dict[str, Any]] = [
            {"name": "Agent", "value": identity.get("name", str(agent_role)), "inline": True},
        ]
        if tokens_used:
            fields.append({"name": "Tokens", "value": f"{tokens_used:,}", "inline": True})
        if model_used:
            fields.append({"name": "Model", "value": model_used, "inline": True})

        return await self.notify(
            agent_role=agent_role,
            channel="agent_hub",
            embed_data={
                "title": f"✅ Task Complete: {issue_id}",
                "description": summary[:2000],
                "fields": fields,
            },
            thread_id=thread_id,
        )

    async def send_task_started(
        self,
        agent_role: AgentRole,
        issue_id: str,
        issue_title: str,
        thread_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Send a task started notification."""
        identity = AGENT_IDENTITIES.get(agent_role, {})
        emoji = identity.get("emoji", "⚙️")

        return await self.notify(
            agent_role=agent_role,
            channel="agent_hub",
            embed_data={
                "title": f"{emoji} Processing: {issue_id}",
                "description": f"**{identity.get('name', agent_role)}** is working on: {issue_title}",
                "fields": [
                    {"name": "Issue", "value": issue_id, "inline": True},
                    {"name": "Agent", "value": identity.get("name", str(agent_role)), "inline": True},
                ],
            },
            thread_id=thread_id,
        )

    async def send_alert(
        self,
        agent_role: AgentRole,
        title: str,
        description: str,
    ) -> dict[str, Any] | None:
        """Send a critical alert."""
        return await self.notify(
            agent_role=agent_role,
            channel="alerts",
            embed_data={
                "title": f"🚨 {title}",
                "description": description,
            },
        )

    async def agent_speak(
        self,
        thread_id: str,
        agent_role: AgentRole,
        content: str,
        conversation_store: Any | None = None,
    ) -> dict[str, Any] | None:
        """Send a plain text message via webhook with agent persona (for thread conversations)."""
        url = self._webhook_urls.get("agent_hub")
        if not url:
            return None

        identity = AGENT_IDENTITIES.get(agent_role, {})
        payload: dict[str, Any] = {
            "username": identity.get("name", str(agent_role)),
            "avatar_url": identity.get("avatar_url", ""),
            "content": content[:2000],  # Discord limit
        }

        try:
            request_url = f"{url}?wait=true&thread_id={thread_id}"
            resp = await self._client.post(request_url, json=payload)
            resp.raise_for_status()
            logger.info("Agent %s spoke in thread %s", agent_role, thread_id)

            # Record in conversation store if provided
            if conversation_store:
                from shared.conversation_store import Message
                from datetime import datetime, timezone
                conversation_store.append_message(thread_id, Message(
                    author_type="agent",
                    author_id=str(agent_role),
                    content=content,
                    timestamp=datetime.now(timezone.utc),
                ))

            return resp.json()
        except httpx.HTTPError as e:
            logger.error("Agent speak failed: %s", e)
            return None

    async def send_pipeline_milestone(
        self,
        issue_id: str,
        issue_title: str,
        milestone: str,
        completed_agents: list[str],
        next_agents: list[str],
    ) -> dict[str, Any] | None:
        """Send a pipeline milestone notification to the dashboard."""
        description = f"**{issue_id}**: {issue_title}\n\nMilestone: **{milestone}**"

        fields: list[dict[str, Any]] = []
        if completed_agents:
            fields.append({
                "name": "✅ Completed",
                "value": ", ".join(completed_agents),
                "inline": False,
            })
        if next_agents:
            fields.append({
                "name": "⏭️ Next",
                "value": ", ".join(next_agents),
                "inline": False,
            })

        return await self.notify(
            agent_role=AgentRole.PRODUCT_STRATEGIST,  # Use neutral agent for milestones
            channel="dashboard",
            embed_data={
                "title": f"📊 Pipeline Milestone: {milestone}",
                "description": description,
                "fields": fields,
            },
        )
