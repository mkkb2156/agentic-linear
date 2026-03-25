"""Async GitHub REST API v3 client using httpx."""

from __future__ import annotations

import base64
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GITHUB_API_URL = "https://api.github.com"


class GitHubClient:
    def __init__(self, token: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=GITHUB_API_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def create_branch(
        self, repo: str, branch_name: str, from_branch: str = "main"
    ) -> dict[str, Any]:
        """Create a new branch from an existing branch ref."""
        # Get the SHA of the source branch
        resp = await self._client.get(f"/repos/{repo}/git/ref/heads/{from_branch}")
        resp.raise_for_status()
        sha = resp.json()["object"]["sha"]

        # Create the new branch ref
        resp = await self._client.post(
            f"/repos/{repo}/git/refs",
            json={"ref": f"refs/heads/{branch_name}", "sha": sha},
        )
        resp.raise_for_status()
        logger.info("Created branch %s on %s from %s", branch_name, repo, from_branch)
        return resp.json()

    async def get_file(
        self, repo: str, path: str, branch: str = "main"
    ) -> dict[str, Any]:
        """Get file contents from a repo. Returns dict with 'content' (decoded), 'sha', etc."""
        resp = await self._client.get(
            f"/repos/{repo}/contents/{path}",
            params={"ref": branch},
        )
        resp.raise_for_status()
        data = resp.json()
        # Decode base64 content
        if data.get("content"):
            data["decoded_content"] = base64.b64decode(data["content"]).decode("utf-8")
        return data

    async def push_file(
        self,
        repo: str,
        path: str,
        content: str,
        message: str,
        branch: str,
    ) -> dict[str, Any]:
        """Create or update a file in a repo."""
        encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")

        # Check if file exists to get its SHA (needed for updates)
        payload: dict[str, Any] = {
            "message": message,
            "content": encoded,
            "branch": branch,
        }
        try:
            existing = await self.get_file(repo, path, branch)
            payload["sha"] = existing["sha"]
        except httpx.HTTPStatusError as e:
            if e.response.status_code != 404:
                raise

        resp = await self._client.put(
            f"/repos/{repo}/contents/{path}",
            json=payload,
        )
        resp.raise_for_status()
        logger.info("Pushed file %s to %s@%s", path, repo, branch)
        return resp.json()

    async def create_pull_request(
        self,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str = "main",
    ) -> dict[str, Any]:
        """Create a pull request."""
        resp = await self._client.post(
            f"/repos/{repo}/pulls",
            json={
                "title": title,
                "body": body,
                "head": head,
                "base": base,
            },
        )
        resp.raise_for_status()
        pr = resp.json()
        logger.info("Created PR #%s on %s: %s", pr.get("number"), repo, title)
        return pr
