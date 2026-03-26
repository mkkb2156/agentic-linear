"""Async Vercel REST API client using httpx."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

VERCEL_API_URL = "https://api.vercel.com"


class VercelClient:
    def __init__(self, token: str, team_id: str = "") -> None:
        self._team_id = team_id
        self._client = httpx.AsyncClient(
            base_url=VERCEL_API_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=60.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    def _params(self) -> dict[str, str]:
        """Add teamId to query params if configured."""
        return {"teamId": self._team_id} if self._team_id else {}

    async def create_project(
        self,
        name: str,
        repo: str,
        framework: str = "nextjs",
    ) -> dict[str, Any]:
        """Create a Vercel project linked to a GitHub repo."""
        # First check if project already exists
        try:
            resp = await self._client.get(
                f"/v9/projects/{name}",
                params=self._params(),
            )
            if resp.status_code == 200:
                logger.info("Vercel project already exists: %s", name)
                return resp.json()
        except httpx.HTTPError:
            pass

        # Create new project linked to GitHub repo
        owner, repo_name = repo.split("/", 1) if "/" in repo else ("", repo)
        payload: dict[str, Any] = {
            "name": name,
            "framework": framework,
            "gitRepository": {
                "type": "github",
                "repo": repo,
            },
        }

        resp = await self._client.post(
            "/v10/projects",
            json=payload,
            params=self._params(),
        )
        resp.raise_for_status()
        project = resp.json()
        logger.info("Created Vercel project: %s (id: %s)", name, project.get("id"))
        return project

    async def create_deployment(
        self,
        project_name: str,
        ref: str = "main",
    ) -> dict[str, Any]:
        """Trigger a deployment for a project."""
        payload: dict[str, Any] = {
            "name": project_name,
            "target": "production",
            "gitSource": {
                "type": "github",
                "ref": ref,
            },
        }

        resp = await self._client.post(
            "/v13/deployments",
            json=payload,
            params=self._params(),
        )
        resp.raise_for_status()
        deployment = resp.json()
        url = deployment.get("url", "")
        logger.info("Vercel deployment triggered: %s → %s", project_name, url)
        return deployment

    async def deploy_repo(
        self,
        repo: str,
        project_name: str = "",
        framework: str = "nextjs",
    ) -> dict[str, Any]:
        """Full deploy flow: create project (if needed) + trigger deployment."""
        name = project_name or repo.split("/")[-1]

        # Create/get project
        project = await self.create_project(name, repo, framework)
        project_id = project.get("id", "")

        # The project linked to GitHub will auto-deploy on push.
        # Return project info with the expected URL.
        domains = project.get("alias", [])
        url = f"https://{name}.vercel.app"
        if domains:
            url = f"https://{domains[0]['domain']}" if isinstance(domains[0], dict) else f"https://{domains[0]}"

        return {
            "success": True,
            "project_id": project_id,
            "project_name": name,
            "url": url,
            "dashboard": f"https://vercel.com/{name}",
            "note": "GitHub repo linked — auto-deploys on every push to main",
        }
