"""Setup script — creates custom Linear workflow states + webhook.

Usage:
    LINEAR_API_KEY=lin_api_xxx python scripts/setup_linear.py

This creates the 8 pipeline states needed for agent handoffs,
and optionally sets up the webhook pointing to your gateway URL.
"""

from __future__ import annotations

import asyncio
import os
import sys

import httpx

LINEAR_API_URL = "https://api.linear.app/graphql"

# Pipeline states to create (in order)
# type: "started" means in-progress, "completed" means done
PIPELINE_STATES = [
    {"name": "Strategy Complete", "type": "started", "color": "#003232", "position": 10},
    {"name": "Spec Complete", "type": "started", "color": "#4ECDC4", "position": 11},
    {"name": "Architecture Complete", "type": "started", "color": "#7C4DFF", "position": 12},
    {"name": "Implementation Done", "type": "started", "color": "#FF6E40", "position": 13},
    {"name": "QA Passed", "type": "started", "color": "#FF4081", "position": 14},
    {"name": "Deployed", "type": "started", "color": "#FFD740", "position": 15},
    {"name": "Deploy Complete", "type": "completed", "color": "#69F0AE", "position": 16},
    {"name": "Alert Triggered", "type": "started", "color": "#FF1744", "position": 17},
]


async def graphql(client: httpx.AsyncClient, query: str, variables: dict | None = None) -> dict:
    payload: dict = {"query": query}
    if variables:
        payload["variables"] = variables
    resp = await client.post(LINEAR_API_URL, json=payload)
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        print(f"  ERROR: {data['errors']}")
        return {}
    return data.get("data", {})


async def get_team(client: httpx.AsyncClient, team_name: str) -> dict:
    """Find team by name."""
    data = await graphql(client, """
        query { teams { nodes { id name key } } }
    """)
    for team in data.get("teams", {}).get("nodes", []):
        if team["name"] == team_name or team["key"] == team_name:
            return team
    return {}


async def get_existing_states(client: httpx.AsyncClient, team_id: str) -> list[str]:
    """Get existing workflow state names for a team."""
    data = await graphql(client, """
        query($teamId: String!) {
            team(id: $teamId) { states { nodes { id name type } } }
        }
    """, {"teamId": team_id})
    states = data.get("team", {}).get("states", {}).get("nodes", [])
    return [s["name"] for s in states]


async def create_workflow_state(
    client: httpx.AsyncClient, team_id: str, name: str, state_type: str, color: str, position: int
) -> dict:
    """Create a workflow state for a team."""
    data = await graphql(client, """
        mutation CreateState($input: WorkflowStateCreateInput!) {
            workflowStateCreate(input: $input) {
                success
                workflowState { id name type position }
            }
        }
    """, {
        "input": {
            "teamId": team_id,
            "name": name,
            "type": state_type,
            "color": color,
            "position": position,
        }
    })
    return data.get("workflowStateCreate", {})


async def create_webhook(client: httpx.AsyncClient, team_id: str, url: str, secret: str) -> dict:
    """Create a Linear webhook for issue status changes."""
    data = await graphql(client, """
        mutation CreateWebhook($input: WebhookCreateInput!) {
            webhookCreate(input: $input) {
                success
                webhook { id url enabled }
            }
        }
    """, {
        "input": {
            "url": url,
            "teamId": team_id,
            "resourceTypes": ["Issue"],
            "secret": secret,
            "enabled": True,
            "label": "GDS Agent Pipeline",
        }
    })
    return data.get("webhookCreate", {})


async def main() -> None:
    api_key = os.environ.get("LINEAR_API_KEY", "")
    if not api_key:
        print("ERROR: LINEAR_API_KEY environment variable not set")
        sys.exit(1)

    team_name = os.environ.get("LINEAR_TEAM", "Drone168")
    webhook_url = os.environ.get("GATEWAY_URL", "")
    webhook_secret = os.environ.get("LINEAR_WEBHOOK_SECRET", "")

    async with httpx.AsyncClient(
        headers={"Authorization": api_key, "Content-Type": "application/json"},
        timeout=30.0,
    ) as client:
        # Find team
        team = await get_team(client, team_name)
        if not team:
            print(f"ERROR: Team '{team_name}' not found")
            sys.exit(1)
        print(f"Team: {team['name']} ({team['key']}) — {team['id']}")

        # Get existing states
        existing = await get_existing_states(client, team["id"])
        print(f"Existing states: {', '.join(existing)}")

        # Create pipeline states
        print("\n--- Creating Pipeline Workflow States ---")
        created = 0
        for state in PIPELINE_STATES:
            if state["name"] in existing:
                print(f"  SKIP: '{state['name']}' already exists")
                continue

            result = await create_workflow_state(
                client,
                team_id=team["id"],
                name=state["name"],
                state_type=state["type"],
                color=state["color"],
                position=state["position"],
            )
            if result.get("success"):
                ws = result.get("workflowState", {})
                print(f"  CREATED: '{ws.get('name')}' (type={ws.get('type')}, id={ws.get('id')})")
                created += 1
            else:
                print(f"  FAILED: '{state['name']}'")

        print(f"\n{created} states created, {len(PIPELINE_STATES) - created} skipped")

        # Create webhook (if URL provided)
        if webhook_url:
            print("\n--- Creating Linear Webhook ---")
            full_url = f"{webhook_url.rstrip('/')}/webhooks/linear"
            result = await create_webhook(client, team["id"], full_url, webhook_secret)
            if result.get("success"):
                wh = result.get("webhook", {})
                print(f"  CREATED: webhook → {wh.get('url')} (id={wh.get('id')})")
            else:
                print(f"  FAILED: webhook creation")
        else:
            print("\nSKIP: No GATEWAY_URL set — webhook not created")
            print("  To create later: GATEWAY_URL=https://your-app.railway.app python scripts/setup_linear.py")

        # Verify final state
        print("\n--- Final Workflow States ---")
        final_states = await get_existing_states(client, team["id"])
        for s in final_states:
            marker = " ✓" if s in [ps["name"] for ps in PIPELINE_STATES] else ""
            print(f"  • {s}{marker}")


if __name__ == "__main__":
    asyncio.run(main())
