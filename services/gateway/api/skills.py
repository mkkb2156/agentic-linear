"""Dashboard API — Skills management (domain knowledge files)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/skills", tags=["skills"])


class SkillUpdate(BaseModel):
    content: str


class SkillCreate(BaseModel):
    name: str
    content: str


@router.get("")
async def list_skills(request: Request) -> list[dict[str, Any]]:
    """List all skill files."""
    config_manager = request.app.state.config_manager
    skills = config_manager.list_skills()
    result = []
    for skill_name in skills:
        content = config_manager.read_skill(skill_name)
        result.append({
            "name": skill_name,
            "line_count": len(content.split("\n")) if content else 0,
            "preview": content[:200] if content else "",
        })
    return result


@router.get("/{name}")
async def get_skill(request: Request, name: str) -> dict[str, Any]:
    """Get skill content."""
    config_manager = request.app.state.config_manager
    content = config_manager.read_skill(name)
    if content is None:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")
    return {"name": name, "content": content}


@router.put("/{name}")
async def update_skill(request: Request, name: str, body: SkillUpdate) -> dict[str, str]:
    """Update skill content."""
    config_manager = request.app.state.config_manager
    config_manager.write_skill(name, body.content)
    return {"status": "updated"}


@router.post("")
async def create_skill(request: Request, body: SkillCreate) -> dict[str, str]:
    """Create a new skill file."""
    config_manager = request.app.state.config_manager
    existing = config_manager.read_skill(body.name)
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"Skill '{body.name}' already exists")
    config_manager.write_skill(body.name, body.content)
    return {"status": "created"}


@router.delete("/{name}")
async def delete_skill(request: Request, name: str) -> dict[str, str]:
    """Delete a skill file."""
    config_manager = request.app.state.config_manager
    content = config_manager.read_skill(name)
    if content is None:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")
    config_manager.delete_skill(name)
    return {"status": "deleted"}
