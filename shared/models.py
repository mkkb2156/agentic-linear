from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AgentRole(StrEnum):
    PRODUCT_STRATEGIST = "product_strategist"
    SPEC_ARCHITECT = "spec_architect"
    SYSTEM_ARCHITECT = "system_architect"
    FRONTEND_ENGINEER = "frontend_engineer"
    BACKEND_ENGINEER = "backend_engineer"
    QA_ENGINEER = "qa_engineer"
    DEVOPS = "devops"
    RELEASE_MANAGER = "release_manager"
    INFRA_OPS = "infra_ops"
    CLOUD_OPS = "cloud_ops"
    ADMIN = "admin"


class LinearWebhookPayload(BaseModel):
    action: str  # create / update / remove
    type: str  # Issue, Comment, etc.
    data: dict[str, Any] = Field(default_factory=dict)
    updated_from: dict[str, Any] | None = Field(default=None, alias="updatedFrom")
    url: str | None = None
    created_at: str | None = Field(default=None, alias="createdAt")

    model_config = {"populate_by_name": True}


class StatusTransition(BaseModel):
    """Maps a Linear issue status to the agent role(s) it triggers."""

    from_status: str
    agent_role: AgentRole


# Pipeline DAG: status transitions in order
# Each status triggers the next agent(s) in the pipeline
PIPELINE_TRANSITIONS: list[StatusTransition] = [
    StatusTransition(
        from_status="Strategy Complete",
        agent_role=AgentRole.SPEC_ARCHITECT,
    ),
    StatusTransition(
        from_status="Spec Complete",
        agent_role=AgentRole.SYSTEM_ARCHITECT,
    ),
    # Architecture Complete triggers BOTH frontend + backend (parallel)
    StatusTransition(
        from_status="Architecture Complete",
        agent_role=AgentRole.FRONTEND_ENGINEER,
    ),
    StatusTransition(
        from_status="Architecture Complete",
        agent_role=AgentRole.BACKEND_ENGINEER,
    ),
    StatusTransition(
        from_status="Implementation Done",
        agent_role=AgentRole.QA_ENGINEER,
    ),
    StatusTransition(
        from_status="QA Passed",
        agent_role=AgentRole.DEVOPS,
    ),
    StatusTransition(
        from_status="Deployed",
        agent_role=AgentRole.RELEASE_MANAGER,
    ),
    StatusTransition(
        from_status="Alert Triggered",
        agent_role=AgentRole.INFRA_OPS,
    ),
    StatusTransition(
        from_status="Deploy Complete",
        agent_role=AgentRole.CLOUD_OPS,
    ),
]

# Ordered pipeline stages for DAG enforcement
PIPELINE_ORDER: list[str] = [
    "Strategy Complete",
    "Spec Complete",
    "Architecture Complete",
    "Implementation Done",
    "QA Passed",
    "Deployed",
    "Deploy Complete",
]


# Agent identity for Discord (name, emoji, color, avatar_url)
# Avatars use DiceBear Bottts style — deterministic, unique per agent
_AVATAR_BASE = "https://api.dicebear.com/9.x/bottts/png?seed="

AGENT_IDENTITIES: dict[AgentRole, dict[str, str]] = {
    AgentRole.PRODUCT_STRATEGIST: {
        "name": "🎯 策略師",
        "emoji": "🎯",
        "color": "#003232",
        "avatar_url": f"{_AVATAR_BASE}strategist&backgroundColor=003232",
    },
    AgentRole.SPEC_ARCHITECT: {
        "name": "📐 規格師",
        "emoji": "📐",
        "color": "#4ECDC4",
        "avatar_url": f"{_AVATAR_BASE}spec-architect&backgroundColor=4ECDC4",
    },
    AgentRole.SYSTEM_ARCHITECT: {
        "name": "🏗️ 架構師",
        "emoji": "🏗️",
        "color": "#7C4DFF",
        "avatar_url": f"{_AVATAR_BASE}system-architect&backgroundColor=7C4DFF",
    },
    AgentRole.FRONTEND_ENGINEER: {
        "name": "⚛️ 前端工程師",
        "emoji": "⚛️",
        "color": "#00E676",
        "avatar_url": f"{_AVATAR_BASE}frontend-engineer&backgroundColor=00E676",
    },
    AgentRole.BACKEND_ENGINEER: {
        "name": "🔧 後端工程師",
        "emoji": "🔧",
        "color": "#FF6E40",
        "avatar_url": f"{_AVATAR_BASE}backend-engineer&backgroundColor=FF6E40",
    },
    AgentRole.QA_ENGINEER: {
        "name": "🧪 測試工程師",
        "emoji": "🧪",
        "color": "#FF4081",
        "avatar_url": f"{_AVATAR_BASE}qa-engineer&backgroundColor=FF4081",
    },
    AgentRole.DEVOPS: {
        "name": "🚀 部署官",
        "emoji": "🚀",
        "color": "#FFD740",
        "avatar_url": f"{_AVATAR_BASE}devops&backgroundColor=FFD740",
    },
    AgentRole.RELEASE_MANAGER: {
        "name": "📋 發版管理",
        "emoji": "📋",
        "color": "#B388FF",
        "avatar_url": f"{_AVATAR_BASE}release-manager&backgroundColor=B388FF",
    },
    AgentRole.INFRA_OPS: {
        "name": "🖥️ 維運官",
        "emoji": "🖥️",
        "color": "#69F0AE",
        "avatar_url": f"{_AVATAR_BASE}infra-ops&backgroundColor=69F0AE",
    },
    AgentRole.CLOUD_OPS: {
        "name": "☁️ 雲端官",
        "emoji": "☁️",
        "color": "#448AFF",
        "avatar_url": f"{_AVATAR_BASE}cloud-ops&backgroundColor=448AFF",
    },
    AgentRole.ADMIN: {
        "name": "🛡️ 管理官",
        "emoji": "🛡️",
        "color": "#FFD700",
        "avatar_url": f"{_AVATAR_BASE}admin&backgroundColor=FFD700",
    },
}

# Agent personas for Discord webhook messages (username + avatar for conversational mode)
AGENT_PERSONAS: dict[AgentRole, dict[str, str]] = {
    role: {
        "username": identity["name"],
        "avatar_url": identity["avatar_url"],
    }
    for role, identity in AGENT_IDENTITIES.items()
}
