from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

LINEAR_API_URL = "https://api.linear.app/graphql"


class LinearClient:
    def __init__(self, api_key: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=LINEAR_API_URL,
            headers={
                "Authorization": api_key,
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _graphql(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables
        resp = await self._client.post("", json=payload)
        resp.raise_for_status()
        data = resp.json()
        if "errors" in data:
            logger.error("Linear GraphQL errors: %s", data["errors"])
            raise RuntimeError(f"Linear API error: {data['errors']}")
        return data.get("data", {})

    async def get_issue(self, issue_id: str) -> dict[str, Any]:
        query = """
        query GetIssue($id: String!) {
            issue(id: $id) {
                id identifier title description
                state { id name }
                assignee { id name }
                labels { nodes { id name } }
                project { id name }
            }
        }
        """
        data = await self._graphql(query, {"id": issue_id})
        return data.get("issue", {})

    async def update_issue(self, issue_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        query = """
        mutation UpdateIssue($id: String!, $input: IssueUpdateInput!) {
            issueUpdate(id: $id, input: $input) {
                success
                issue { id identifier state { name } }
            }
        }
        """
        data = await self._graphql(query, {"id": issue_id, "input": updates})
        return data.get("issueUpdate", {})

    async def add_comment(self, issue_id: str, body: str) -> dict[str, Any]:
        query = """
        mutation AddComment($issueId: String!, $body: String!) {
            commentCreate(input: { issueId: $issueId, body: $body }) {
                success
                comment { id body }
            }
        }
        """
        data = await self._graphql(query, {"issueId": issue_id, "body": body})
        return data.get("commentCreate", {})

    async def create_issue(self, team_id: str, title: str, **kwargs: Any) -> dict[str, Any]:
        query = """
        mutation CreateIssue($input: IssueCreateInput!) {
            issueCreate(input: $input) {
                success
                issue { id identifier title state { name } }
            }
        }
        """
        input_data: dict[str, Any] = {"teamId": team_id, "title": title, **kwargs}
        data = await self._graphql(query, {"input": input_data})
        return data.get("issueCreate", {})

    async def query_issues(self, filter_input: dict[str, Any]) -> list[dict[str, Any]]:
        query = """
        query ListIssues($filter: IssueFilter) {
            issues(filter: $filter) {
                nodes {
                    id identifier title
                    state { id name }
                    assignee { id name }
                    priority
                }
            }
        }
        """
        data = await self._graphql(query, {"filter": filter_input})
        return data.get("issues", {}).get("nodes", [])


def verify_webhook(body: bytes, signature: str, secret: str) -> bool:
    """Verify Linear webhook HMAC-SHA256 signature."""
    expected = hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
