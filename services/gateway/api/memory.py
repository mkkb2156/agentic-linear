"""Dashboard API — Memory management (souls, project context)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/memory", tags=["memory"])


class MemoryUpdate(BaseModel):
    content: str


# ── Souls ───────────────────────────────────────────────────────────────

@router.get("/souls")
async def list_souls(request: Request) -> list[dict[str, Any]]:
    """List all agent soul files with metadata."""
    soul_manager = request.app.state.soul_manager
    from shared.models import AgentRole, AGENT_IDENTITIES

    souls = []
    for role in AgentRole:
        role_str = str(role)
        content = soul_manager.load(role_str)
        identity = AGENT_IDENTITIES.get(role, {})
        souls.append({
            "role": role_str,
            "name": identity.get("name", role_str),
            "emoji": identity.get("emoji", ""),
            "line_count": soul_manager.line_count(role_str),
            "has_content": bool(content),
        })
    return souls


@router.get("/souls/{role}")
async def get_soul(request: Request, role: str) -> dict[str, Any]:
    """Get soul content for an agent."""
    soul_manager = request.app.state.soul_manager
    content = soul_manager.load(role)
    return {
        "role": role,
        "content": content,
        "line_count": soul_manager.line_count(role),
    }


@router.put("/souls/{role}")
async def update_soul(request: Request, role: str, body: MemoryUpdate) -> dict[str, str]:
    """Update soul content for an agent."""
    soul_manager = request.app.state.soul_manager
    soul_manager.write(role, body.content)
    return {"status": "updated"}


# ── Project Context ─────────────────────────────────────────────────────

@router.get("/projects")
async def list_projects(request: Request) -> list[dict[str, Any]]:
    """List all project contexts."""
    project_context = request.app.state.project_context_manager
    projects_dir = Path(project_context._base_dir)

    projects = []
    if projects_dir.exists():
        for project_dir in sorted(projects_dir.iterdir()):
            if project_dir.is_dir():
                context_file = project_dir / "context.md"
                content = ""
                if context_file.exists():
                    content = context_file.read_text(encoding="utf-8")
                projects.append({
                    "project_id": project_dir.name,
                    "line_count": len(content.split("\n")) if content else 0,
                    "has_content": bool(content.strip()),
                })
    return projects


@router.get("/projects/{project_id}")
async def get_project_context(request: Request, project_id: str) -> dict[str, Any]:
    """Get project context content."""
    project_context = request.app.state.project_context_manager
    content = project_context.load(project_id)
    return {
        "project_id": project_id,
        "content": content,
    }


@router.put("/projects/{project_id}")
async def update_project_context(
    request: Request, project_id: str, body: MemoryUpdate
) -> dict[str, str]:
    """Update project context content."""
    project_context = request.app.state.project_context_manager
    project_context.write(project_id, body.content)
    return {"status": "updated"}
