from __future__ import annotations

from typing import Any

from shared.models import AGENT_IDENTITIES, AgentRole


def build_status_change_embed(
    issue_id: str,
    issue_title: str,
    old_status: str,
    new_status: str,
    agent_role: AgentRole,
) -> dict[str, Any]:
    """Build a Discord embed for an issue status change."""
    identity = AGENT_IDENTITIES.get(agent_role, {})
    color_hex = identity.get("color", "#808080").lstrip("#")

    return {
        "title": f"{identity.get('emoji', '🔄')} {issue_id}: {issue_title}",
        "description": f"**{old_status}** → **{new_status}**",
        "color": int(color_hex, 16),
        "fields": [
            {"name": "Agent", "value": identity.get("name", str(agent_role)), "inline": True},
            {"name": "Status", "value": new_status, "inline": True},
        ],
    }


def build_task_complete_embed(
    issue_id: str,
    agent_role: AgentRole,
    summary: str,
    tokens_used: int = 0,
    model_used: str = "",
) -> dict[str, Any]:
    """Build a Discord embed for task completion."""
    identity = AGENT_IDENTITIES.get(agent_role, {})
    color_hex = identity.get("color", "#808080").lstrip("#")

    fields: list[dict[str, Any]] = [
        {"name": "Agent", "value": identity.get("name", str(agent_role)), "inline": True},
    ]
    if tokens_used:
        fields.append({"name": "Tokens", "value": str(tokens_used), "inline": True})
    if model_used:
        fields.append({"name": "Model", "value": model_used, "inline": True})

    return {
        "title": f"✅ Task Complete: {issue_id}",
        "description": summary,
        "color": int(color_hex, 16),
        "fields": fields,
    }
