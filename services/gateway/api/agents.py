"""Dashboard API — Agent status and configuration endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from shared.models import AgentRole, AGENT_IDENTITIES

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("")
async def list_agents(request: Request) -> list[dict[str, Any]]:
    """List all agents with their live state and identity info."""
    state_tracker = getattr(request.app.state, "state_tracker", None)
    live_states = {}
    if state_tracker:
        live_states = await state_tracker.get_all()

    agents = []
    for role in AgentRole:
        identity = AGENT_IDENTITIES.get(role, {})
        state = live_states.get(str(role), {"status": "idle"})
        agents.append({
            "role": str(role),
            "name": identity.get("name", str(role)),
            "emoji": identity.get("emoji", ""),
            "color": identity.get("color", "#666"),
            "avatar_url": identity.get("avatar_url", ""),
            "state": state,
        })
    return agents


@router.get("/{role}")
async def get_agent(request: Request, role: str) -> dict[str, Any]:
    """Get a single agent's details including config and live state."""
    identity = AGENT_IDENTITIES.get(AgentRole(role), {})
    config_manager = request.app.state.config_manager

    # Load agent YAML config
    agent_config = config_manager.get_agent_config(role)

    # Live state from Redis
    state_tracker = getattr(request.app.state, "state_tracker", None)
    state = {"status": "idle"}
    if state_tracker:
        state = await state_tracker.get_all()
        state = state.get(role, {"status": "idle"})

    return {
        "role": role,
        "name": identity.get("name", role),
        "emoji": identity.get("emoji", ""),
        "color": identity.get("color", "#666"),
        "avatar_url": identity.get("avatar_url", ""),
        "config": agent_config,
        "state": state,
    }


@router.get("/{role}/config")
async def get_agent_config(request: Request, role: str) -> dict[str, Any]:
    """Get agent YAML configuration."""
    config_manager = request.app.state.config_manager
    return config_manager.get_agent_config(role)


@router.put("/{role}/config")
async def update_agent_config(
    request: Request, role: str, body: dict[str, Any]
) -> dict[str, str]:
    """Update agent configuration (model, max_turns, skills, enabled)."""
    config_manager = request.app.state.config_manager
    config_manager.update_agent_config(role, body)
    return {"status": "updated"}
