"""Async GitHub REST API v3 client using httpx."""

from __future__ import annotations

import base64
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GITHUB_API_URL = "https://api.github.com"


class GitHubClient:
    def __init__(self, token: str, owner: str = "") -> None:
        self._owner = owner
        self._client = httpx.AsyncClient(
            base_url=GITHUB_API_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30.0,
        )

    @property
    def owner(self) -> str:
        return self._owner

    async def close(self) -> None:
        await self._client.aclose()

    def _full_repo(self, repo: str) -> str:
        """Ensure repo is in 'owner/name' format."""
        if "/" in repo:
            return repo
        return f"{self._owner}/{repo}" if self._owner else repo

    # ---- Repo management ----

    async def list_repos(self, per_page: int = 30) -> list[dict[str, Any]]:
        """List repos for the authenticated user."""
        resp = await self._client.get(
            "/user/repos",
            params={"per_page": per_page, "sort": "updated", "affiliation": "owner"},
        )
        resp.raise_for_status()
        return resp.json()

    async def search_repos(self, query: str) -> list[dict[str, Any]]:
        """Search repos by name/description within the owner's account."""
        q = f"{query} user:{self._owner}" if self._owner else query
        resp = await self._client.get(
            "/search/repositories",
            params={"q": q, "per_page": 10},
        )
        resp.raise_for_status()
        return resp.json().get("items", [])

    async def create_repo(
        self, name: str, description: str = "", private: bool = False
    ) -> dict[str, Any]:
        """Create a new repository."""
        resp = await self._client.post(
            "/user/repos",
            json={
                "name": name,
                "description": description,
                "private": private,
                "auto_init": True,  # Creates initial commit with README
            },
        )
        resp.raise_for_status()
        repo = resp.json()
        logger.info("Created repo %s (private=%s)", repo.get("full_name"), private)
        return repo

    async def find_or_create_repo(
        self, name: str, description: str = "", private: bool = False
    ) -> dict[str, Any]:
        """Find an existing repo by name, or create it if it doesn't exist."""
        full = self._full_repo(name)
        try:
            resp = await self._client.get(f"/repos/{full}")
            if resp.status_code == 200:
                logger.info("Found existing repo: %s", full)
                return resp.json()
        except httpx.HTTPError:
            pass

        return await self.create_repo(
            name=name.split("/")[-1],
            description=description,
            private=private,
        )

    # ---- Branch management ----

    async def create_branch(
        self, repo: str, branch_name: str, from_branch: str = "main"
    ) -> dict[str, Any]:
        """Create a new branch from an existing branch ref."""
        full = self._full_repo(repo)
        resp = await self._client.get(f"/repos/{full}/git/ref/heads/{from_branch}")
        resp.raise_for_status()
        sha = resp.json()["object"]["sha"]

        resp = await self._client.post(
            f"/repos/{full}/git/refs",
            json={"ref": f"refs/heads/{branch_name}", "sha": sha},
        )
        resp.raise_for_status()
        logger.info("Created branch %s on %s from %s", branch_name, full, from_branch)
        return resp.json()

    # ---- File operations ----

    async def get_file(
        self, repo: str, path: str, branch: str = "main"
    ) -> dict[str, Any]:
        """Get file contents from a repo."""
        full = self._full_repo(repo)
        resp = await self._client.get(
            f"/repos/{full}/contents/{path}",
            params={"ref": branch},
        )
        resp.raise_for_status()
        data = resp.json()
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
        full = self._full_repo(repo)
        encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")

        payload: dict[str, Any] = {
            "message": message,
            "content": encoded,
            "branch": branch,
        }
        try:
            existing = await self.get_file(full, path, branch)
            payload["sha"] = existing["sha"]
        except httpx.HTTPStatusError as e:
            if e.response.status_code != 404:
                raise

        resp = await self._client.put(
            f"/repos/{full}/contents/{path}",
            json=payload,
        )
        resp.raise_for_status()
        logger.info("Pushed file %s to %s@%s", path, full, branch)
        return resp.json()

    # ---- Pull requests ----

    async def create_pull_request(
        self,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str = "main",
    ) -> dict[str, Any]:
        """Create a pull request."""
        full = self._full_repo(repo)
        resp = await self._client.post(
            f"/repos/{full}/pulls",
            json={
                "title": title,
                "body": body,
                "head": head,
                "base": base,
            },
        )
        resp.raise_for_status()
        pr = resp.json()
        logger.info("Created PR #%s on %s: %s", pr.get("number"), full, title)
        return pr

    async def merge_pull_request(
        self,
        repo: str,
        pr_number: int,
        merge_method: str = "squash",
    ) -> dict[str, Any]:
        """Merge a pull request."""
        full = self._full_repo(repo)
        resp = await self._client.put(
            f"/repos/{full}/pulls/{pr_number}/merge",
            json={"merge_method": merge_method},
        )
        resp.raise_for_status()
        logger.info("Merged PR #%s on %s (method=%s)", pr_number, full, merge_method)
        return resp.json()
