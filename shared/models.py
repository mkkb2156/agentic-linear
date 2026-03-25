from __future__ import annotations

import uuid
from datetime import datetime
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


class QueueName(StrEnum):
    PLANNING = "planning"
    BUILD = "build"
    VERIFY = "verify"
    OPS = "ops"


class TaskStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD = "dead"


class AgentTask(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    queue_name: QueueName
    agent_role: AgentRole
    issue_id: str
    project_id: uuid.UUID | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    retry_count: int = 0
    max_retries: int = 3
    model_used: str | None = None
    tokens_used: int = 0
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    idempotency_key: str | None = None


class LinearWebhookPayload(BaseModel):
    action: str  # create / update / remove
    type: str  # Issue, Comment, etc.
    data: dict[str, Any] = Field(default_factory=dict)
    updated_from: dict[str, Any] | None = Field(default=None, alias="updatedFrom")
    url: str | None = None
    created_at: str | None = Field(default=None, alias="createdAt")

    model_config = {"populate_by_name": True}


class StatusTransition(BaseModel):
    """Maps a Linear issue status to the target queue and agent role."""

    from_status: str
    queue_name: QueueName
    agent_role: AgentRole


# Pipeline DAG: status transitions in order
# Each status triggers the next agent(s) in the pipeline
PIPELINE_TRANSITIONS: list[StatusTransition] = [
    StatusTransition(
        from_status="Strategy Complete",
        queue_name=QueueName.PLANNING,
        agent_role=AgentRole.SPEC_ARCHITECT,
    ),
    StatusTransition(
        from_status="Spec Complete",
        queue_name=QueueName.PLANNING,
        agent_role=AgentRole.SYSTEM_ARCHITECT,
    ),
    # Architecture Complete triggers BOTH frontend + backend (parallel)
    StatusTransition(
        from_status="Architecture Complete",
        queue_name=QueueName.BUILD,
        agent_role=AgentRole.FRONTEND_ENGINEER,
    ),
    StatusTransition(
        from_status="Architecture Complete",
        queue_name=QueueName.BUILD,
        agent_role=AgentRole.BACKEND_ENGINEER,
    ),
    StatusTransition(
        from_status="Implementation Done",
        queue_name=QueueName.VERIFY,
        agent_role=AgentRole.QA_ENGINEER,
    ),
    StatusTransition(
        from_status="QA Passed",
        queue_name=QueueName.VERIFY,
        agent_role=AgentRole.DEVOPS,
    ),
    StatusTransition(
        from_status="Deployed",
        queue_name=QueueName.VERIFY,
        agent_role=AgentRole.RELEASE_MANAGER,
    ),
    StatusTransition(
        from_status="Alert Triggered",
        queue_name=QueueName.OPS,
        agent_role=AgentRole.INFRA_OPS,
    ),
    StatusTransition(
        from_status="Deploy Complete",
        queue_name=QueueName.OPS,
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


# Agent identity for Discord
AGENT_IDENTITIES: dict[AgentRole, dict[str, str]] = {
    AgentRole.PRODUCT_STRATEGIST: {
        "name": "🎯 策略師",
        "emoji": "🎯",
        "color": "#003232",
    },
    AgentRole.SPEC_ARCHITECT: {
        "name": "📐 規格師",
        "emoji": "📐",
        "color": "#4ECDC4",
    },
    AgentRole.SYSTEM_ARCHITECT: {
        "name": "🏗️ 架構師",
        "emoji": "🏗️",
        "color": "#7C4DFF",
    },
    AgentRole.FRONTEND_ENGINEER: {
        "name": "⚛️ 前端工程師",
        "emoji": "⚛️",
        "color": "#00E676",
    },
    AgentRole.BACKEND_ENGINEER: {
        "name": "🔧 後端工程師",
        "emoji": "🔧",
        "color": "#FF6E40",
    },
    AgentRole.QA_ENGINEER: {
        "name": "🧪 測試工程師",
        "emoji": "🧪",
        "color": "#FF4081",
    },
    AgentRole.DEVOPS: {
        "name": "🚀 部署官",
        "emoji": "🚀",
        "color": "#FFD740",
    },
    AgentRole.RELEASE_MANAGER: {
        "name": "📋 發版管理",
        "emoji": "📋",
        "color": "#B388FF",
    },
    AgentRole.INFRA_OPS: {
        "name": "🖥️ 維運官",
        "emoji": "🖥️",
        "color": "#69F0AE",
    },
    AgentRole.CLOUD_OPS: {
        "name": "☁️ 雲端官",
        "emoji": "☁️",
        "color": "#448AFF",
    },
}
