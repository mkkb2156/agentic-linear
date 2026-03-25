"""Base agent class with Claude Tool Use agentic loop.

Tasks are dicts derived from Linear webhook payloads — no database dependency.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from shared.claude_client import ClaudeClient
from shared.discord_notifier import DiscordNotifier
from shared.linear_client import LinearClient
from shared.models import AgentRole

logger = logging.getLogger(__name__)

# Maximum tool-use turns to prevent runaway loops
MAX_TURNS = 15


class AgentTask:
    """Lightweight task object built from webhook payload — replaces asyncpg.Record."""

    def __init__(
        self,
        issue_id: str,
        agent_role: str,
        payload: dict[str, Any],
    ) -> None:
        self.issue_id = issue_id
        self.agent_role = agent_role
        self.payload = payload

    def __getitem__(self, key: str) -> Any:
        """Dict-like access for backward compatibility."""
        return getattr(self, key)


class BaseAgent:
    """
    Base class for all pipeline agents.

    Subclasses define:
      - role: AgentRole
      - system_prompt: str
      - tools: list of tool defs
    Then call `run()` which executes an agentic loop with Claude.
    """

    role: AgentRole
    system_prompt: str
    tools: list[dict[str, Any]]

    def __init__(
        self,
        claude_client: ClaudeClient,
        linear_client: LinearClient,
        discord_notifier: DiscordNotifier,
    ) -> None:
        self.claude = claude_client
        self.linear = linear_client
        self.discord = discord_notifier

    async def run(self, task: AgentTask) -> dict[str, Any]:
        """
        Execute the agentic loop:
        1. Build initial message from task payload
        2. Call Claude with tools
        3. Process tool calls, feed results back
        4. Repeat until complete_task is called or max turns reached

        Returns dict with 'summary', 'next_status', 'tokens_used', 'model_used'.
        """
        payload = task.payload
        issue_id = task.issue_id

        # Fetch full issue context from Linear
        issue = await self._fetch_issue_context(payload)
        issue_title = issue.get("title", "Unknown")
        # Track the UUID for API calls (different from identifier like DRO-19)
        issue_uuid = issue.get("id", payload.get("event", {}).get("data", {}).get("id", ""))
        logger.info("[%s] issue_id=%s, issue_uuid=%s", self.role, issue_id, issue_uuid)

        # Notify Discord that we're starting
        await self.discord.send_task_started(
            agent_role=self.role,
            issue_id=issue_id,
            issue_title=issue_title,
        )

        # Build initial user message
        user_message = self._build_user_message(issue, payload)

        messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]
        total_tokens = 0
        model_used = ""
        result: dict[str, Any] = {}

        for turn in range(MAX_TURNS):
            response, tokens, model = await self.claude.execute(
                agent_role=self.role,
                system_prompt=self.system_prompt,
                messages=messages,
                tools=self.tools,
            )
            total_tokens += tokens
            model_used = model

            # Check if Claude wants to use tools
            if response.stop_reason == "tool_use":
                # Process all tool calls in this response
                tool_results = []
                complete_result = None

                for block in response.content:
                    if block.type == "tool_use":
                        tool_result, is_complete = await self._handle_tool_call(
                            block.name, block.input, issue_uuid
                        )
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(tool_result),
                        })
                        if is_complete:
                            complete_result = tool_result

                # Add assistant message + tool results to conversation
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

                if complete_result:
                    result = {
                        "summary": complete_result.get("summary", ""),
                        "next_status": complete_result.get("next_status", ""),
                        "tokens_used": total_tokens,
                        "model_used": model_used,
                    }
                    break
            else:
                # Claude responded with text only (no more tool calls)
                text = "".join(
                    b.text for b in response.content if hasattr(b, "text")
                )
                logger.info("[%s] Final response: %s", self.role, text[:200])
                result = {
                    "summary": text[:500],
                    "next_status": "",
                    "tokens_used": total_tokens,
                    "model_used": model_used,
                }
                break
        else:
            logger.warning("[%s] Max turns (%d) reached", self.role, MAX_TURNS)
            result = {
                "summary": "Agent reached maximum turns without completing",
                "next_status": "",
                "tokens_used": total_tokens,
                "model_used": model_used,
            }

        # Transition Linear status if specified
        if result.get("next_status"):
            await self._transition_status(issue_id, payload, result["next_status"])

        # Notify Discord with token/model info
        await self.discord.send_task_complete(
            agent_role=self.role,
            issue_id=issue_id,
            summary=result.get("summary", "Task processed"),
            tokens_used=result.get("tokens_used", 0),
            model_used=result.get("model_used", ""),
        )

        return result

    async def _fetch_issue_context(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Fetch full issue data + comments from Linear. Falls back to payload data."""
        event_data = payload.get("event", {}).get("data", {})
        issue_uuid = event_data.get("id", "")

        if issue_uuid:
            try:
                issue = await self.linear.get_issue(issue_uuid)
                # Fetch comments from previous agents
                try:
                    comments = await self.linear.get_issue_comments(issue_uuid)
                    issue["_comments"] = comments
                except Exception:
                    issue["_comments"] = []
                return issue
            except Exception as e:
                logger.warning("Failed to fetch issue from Linear: %s", e)

        return event_data

    def _build_user_message(self, issue: dict[str, Any], payload: dict[str, Any]) -> str:
        """Build the initial user message with issue context."""
        old_status = payload.get("old_status", "Unknown")
        new_status = payload.get("new_status", "Unknown")

        parts = [
            "## Task Assignment",
            "",
            f"A Linear issue has transitioned from **{old_status}** to **{new_status}**.",
            "You need to process this issue according to your role.",
            "",
            "### Issue Details",
            f"- **ID**: {issue.get('identifier', issue.get('id', 'N/A'))}",
            f"- **Title**: {issue.get('title', 'N/A')}",
            "- **Description**:",
            f"{issue.get('description', 'No description provided.')}",
            "",
        ]

        # Add project context if available
        project = issue.get("project", {})
        if project:
            parts.extend([
                "### Project",
                f"- **Name**: {project.get('name', 'N/A')}",
                "",
            ])

        # Add labels
        labels = issue.get("labels", {}).get("nodes", [])
        if labels:
            label_names = ", ".join(lbl.get("name", "") for lbl in labels)
            parts.append(f"**Labels**: {label_names}")
            parts.append("")

        # Add previous agent comments (pipeline context)
        comments = issue.get("_comments", [])
        if comments:
            parts.append("### Previous Agent Outputs")
            for comment in comments:
                user_name = comment.get("user", {}).get("name", "Unknown")
                body = comment.get("body", "")
                if body:
                    parts.append(f"\n**{user_name}**:\n{body[:2000]}")
            parts.append("")

        parts.extend([
            "### Instructions",
            "1. Analyze the issue and perform your role's responsibilities",
            "2. Post your deliverables as a comment on the issue",
            "3. Call `complete_task` with a summary and the next pipeline status",
            "",
            "### Language Requirement",
            "你必須使用繁體中文回覆所有 Linear comment 和 Discord 通知。",
            "技術術語可保留英文，但描述和分析請使用中文。",
        ])

        return "\n".join(parts)

    async def _handle_tool_call(
        self, tool_name: str, tool_input: dict[str, Any], issue_id: str
    ) -> tuple[dict[str, Any], bool]:
        """
        Execute a tool call and return (result, is_complete).
        is_complete=True when complete_task is called.
        """
        try:
            # Auto-resolve issue_id: Claude often passes identifier (DRO-20)
            # but Linear API needs UUID. Override with tracked UUID.
            if "issue_id" in tool_input and issue_id:
                logger.info(
                    "[%s] Tool %s: replacing issue_id %s → %s",
                    self.role, tool_name, tool_input["issue_id"], issue_id,
                )
                tool_input["issue_id"] = issue_id

            logger.info("[%s] Executing tool: %s (input keys: %s)", self.role, tool_name, list(tool_input.keys()))

            if tool_name == "linear_update_issue":
                return await self._tool_linear_update(tool_input), False

            elif tool_name == "linear_add_comment":
                return await self._tool_linear_comment(tool_input), False

            elif tool_name == "linear_create_issue":
                return await self._tool_linear_create(tool_input, issue_id), False

            elif tool_name == "linear_query_issues":
                return await self._tool_linear_query(tool_input), False

            elif tool_name == "discord_notify":
                return await self._tool_discord_notify(tool_input), False

            elif tool_name == "complete_task":
                return tool_input, True

            else:
                return {"error": f"Unknown tool: {tool_name}"}, False

        except Exception as e:
            logger.error("[%s] Tool %s FAILED: %s", self.role, tool_name, e)
            return {"error": str(e)}, False

    async def _tool_linear_update(self, inp: dict[str, Any]) -> dict[str, Any]:
        issue_id = inp["issue_id"]
        updates: dict[str, Any] = {}

        if "description" in inp:
            updates["description"] = inp["description"]

        if "state_name" in inp:
            state_id = await self.linear.find_state_id(issue_id, inp["state_name"])
            if state_id:
                updates["stateId"] = state_id
            else:
                return {"error": f"State '{inp['state_name']}' not found"}

        result = await self.linear.update_issue(issue_id, updates)
        return {"success": result.get("success", False), "issue": result.get("issue", {})}

    async def _tool_linear_comment(self, inp: dict[str, Any]) -> dict[str, Any]:
        result = await self.linear.add_comment(inp["issue_id"], inp["body"])
        return {"success": result.get("success", False)}

    async def _tool_linear_create(
        self, inp: dict[str, Any], issue_id: str = ""
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        if "description" in inp:
            kwargs["description"] = inp["description"]
        if "parent_id" in inp:
            # Use tracked UUID if Claude passed the identifier (e.g. DRO-20)
            parent = inp["parent_id"]
            kwargs["parentId"] = issue_id if issue_id and not self._is_uuid(parent) else parent

        # Resolve team_id from the current issue's team context
        team_id = await self._resolve_team_id(issue_id)
        if not team_id:
            return {"error": "Could not resolve team ID from issue context"}

        result = await self.linear.create_issue(
            team_id=team_id,
            title=inp["title"],
            **kwargs,
        )
        return {
            "success": result.get("success", False),
            "issue": result.get("issue", {}),
        }

    @staticmethod
    def _is_uuid(value: str) -> bool:
        """Check if a string looks like a UUID."""
        import re
        return bool(re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", value))

    async def _resolve_team_id(self, issue_id: str) -> str:
        """Get team ID from the current issue's context."""
        if hasattr(self, "_cached_team_id") and self._cached_team_id:
            return self._cached_team_id
        try:
            data = await self.linear._graphql("""
                query($id: String!) { issue(id: $id) { team { id } } }
            """, {"id": issue_id})
            team_id = data.get("issue", {}).get("team", {}).get("id", "")
            self._cached_team_id = team_id
            return team_id
        except Exception as e:
            logger.error("Failed to resolve team ID: %s", e)
            return ""

    async def _tool_linear_query(self, inp: dict[str, Any]) -> dict[str, Any]:
        filter_input: dict[str, Any] = {}
        if "state_name" in inp:
            filter_input["state"] = {"name": {"eq": inp["state_name"]}}
        if "query" in inp:
            filter_input["title"] = {"contains": inp["query"]}

        issues = await self.linear.query_issues(filter_input)
        return {"issues": issues[:10]}

    async def _tool_discord_notify(self, inp: dict[str, Any]) -> dict[str, Any]:
        await self.discord.notify(
            agent_role=self.role,
            channel=inp["channel"],
            embed_data={
                "title": inp["title"],
                "description": inp["description"],
            },
        )
        return {"success": True}

    async def _transition_status(
        self, issue_id: str, payload: dict[str, Any], next_status: str
    ) -> None:
        """Update the Linear issue status to trigger the next pipeline agent."""
        event_data = payload.get("event", {}).get("data", {})
        issue_uuid = event_data.get("id", "")

        if not issue_uuid:
            logger.warning("Cannot transition status: no issue UUID")
            return

        try:
            result = await self.linear.transition_issue(issue_uuid, next_status)
            logger.info(
                "[%s] Transitioned issue %s to status: %s (success=%s)",
                self.role,
                issue_id,
                next_status,
                result.get("success", False),
            )
        except ValueError as e:
            logger.error("Failed to transition status: %s", e)
        except Exception as e:
            logger.error("Failed to transition status: %s", e)
