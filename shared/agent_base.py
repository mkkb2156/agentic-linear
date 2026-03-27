"""Base agent class with Claude Tool Use agentic loop.

Tasks are dicts derived from Linear webhook payloads — no database dependency.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from shared.claude_client import ClaudeClient
from shared.discord_notifier import DiscordNotifier
from shared.github_client import GitHubClient
from shared.linear_client import LinearClient
from shared.vercel_client import VercelClient
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
        github_client: GitHubClient | None = None,
        vercel_client: VercelClient | None = None,
    ) -> None:
        self.claude = claude_client
        self.linear = linear_client
        self.discord = discord_notifier
        self.github = github_client
        self.vercel = vercel_client
        self._conversation_store = None  # Set by dispatcher
        self._project_context = None  # Set by dispatcher
        self._thread_id: str | None = None  # Set by dispatcher
        self._project_id: str | None = None  # Set by dispatcher

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

        # Extract memory components from payload (injected by dispatcher)
        self._conversation_store = payload.pop("_conversation_store", None)
        self._project_context = payload.pop("_project_context", None)
        soul_manager = payload.pop("_soul_manager", None)
        self._thread_id = payload.get("thread_id")
        self._project_id = payload.get("project_id")

        # Load config-enhanced system prompt with memory layers
        from shared.agent_config import get_config_manager
        config_mgr = get_config_manager()

        soul_content = ""
        if soul_manager:
            soul_content = soul_manager.load(str(self.role))

        project_context_content = ""
        if self._project_context and self._project_id:
            project_context_content = self._project_context.load(self._project_id)

        conversation_context = ""
        if self._conversation_store and self._thread_id:
            conversation_context = self._conversation_store.format_for_agent(self._thread_id)

        effective_prompt = config_mgr.build_system_prompt(
            str(self.role),
            self.system_prompt,
            soul_content=soul_content,
            project_context=project_context_content,
            conversation_context=conversation_context,
        )

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
                system_prompt=effective_prompt,
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
                # Claude responded with text only (no tool calls)
                text = "".join(
                    b.text for b in response.content if hasattr(b, "text")
                )

                # If this is an early turn and Claude described actions instead
                # of executing them, nudge it to use tools
                if turn < MAX_TURNS - 2:
                    logger.info("[%s] Text response at turn %d, nudging to use tools: %s", self.role, turn, text[:200])
                    messages.append({"role": "assistant", "content": response.content})
                    messages.append({"role": "user", "content": (
                        "請不要描述你要做什麼，直接使用工具執行。"
                        "使用 linear_add_comment 發布你的分析結果，"
                        "然後呼叫 complete_task 完成任務。"
                    )})
                    continue

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

        # Reflect and potentially update soul
        if soul_manager and result.get("summary"):
            try:
                await self._maybe_reflect(soul_manager, task, result)
            except Exception as e:
                logger.warning("Soul reflection failed: %s", e)

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

            elif tool_name == "github_list_repos":
                return await self._tool_github_list_repos(tool_input), False

            elif tool_name == "github_create_repo":
                return await self._tool_github_create_repo(tool_input), False

            elif tool_name == "github_create_pr":
                return await self._tool_github_create_pr(tool_input), False

            elif tool_name == "github_read_file":
                return await self._tool_github_read_file(tool_input), False

            elif tool_name == "vercel_deploy":
                return await self._tool_vercel_deploy(tool_input), False

            elif tool_name == "vercel_check_deploy":
                return await self._tool_vercel_check_deploy(tool_input), False

            elif tool_name == "github_merge_pr":
                return await self._tool_github_merge_pr(tool_input), False

            elif tool_name == "complete_task":
                return tool_input, True

            elif tool_name == "discord_ask_user":
                return await self._tool_discord_ask_user(tool_input), False

            elif tool_name == "discord_discuss":
                return await self._tool_discord_discuss(tool_input), False

            elif tool_name == "discord_report_blocker":
                return await self._tool_discord_report_blocker(tool_input), False

            elif tool_name == "update_project_context":
                return await self._tool_update_project_context(tool_input), False

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

    async def _tool_github_list_repos(self, inp: dict[str, Any]) -> dict[str, Any]:
        if not self.github:
            logger.error("[%s] GitHub client is None! GITHUB_TOKEN likely not set in env.", self.role)
            return {"error": "GitHub client not configured. GITHUB_TOKEN env var is missing."}
        search = inp.get("search", "")
        if search:
            repos = await self.github.search_repos(search)
        else:
            repos = await self.github.list_repos()
        return {
            "repos": [
                {"name": r["name"], "full_name": r["full_name"], "description": r.get("description", "")}
                for r in repos[:20]
            ]
        }

    async def _tool_github_create_repo(self, inp: dict[str, Any]) -> dict[str, Any]:
        if not self.github:
            logger.error("[%s] GitHub client is None! GITHUB_TOKEN likely not set in env.", self.role)
            return {"error": "GitHub client not configured. GITHUB_TOKEN env var is missing."}
        repo = await self.github.find_or_create_repo(
            name=inp["name"],
            description=inp.get("description", ""),
            private=inp.get("private", False),
        )
        return {
            "success": True,
            "full_name": repo.get("full_name", ""),
            "html_url": repo.get("html_url", ""),
            "created": repo.get("created_at", ""),
        }

    async def _tool_github_create_pr(self, inp: dict[str, Any]) -> dict[str, Any]:
        if not self.github:
            logger.error("[%s] GitHub client is None! GITHUB_TOKEN likely not set in env.", self.role)
            return {"error": "GitHub client not configured. GITHUB_TOKEN env var is missing."}
        repo = inp["repo"]
        branch_name = inp["branch_name"]

        await self.github.create_branch(repo, branch_name)

        for f in inp["files"]:
            await self.github.push_file(
                repo=repo,
                path=f["path"],
                content=f["content"],
                message=f"feat: {inp['title']} — {f['path']}",
                branch=branch_name,
            )

        pr = await self.github.create_pull_request(
            repo=repo,
            title=inp["title"],
            body=inp.get("body", ""),
            head=branch_name,
        )
        return {"success": True, "pr_url": pr.get("html_url", ""), "pr_number": pr.get("number")}

    async def _tool_github_read_file(self, inp: dict[str, Any]) -> dict[str, Any]:
        if not self.github:
            logger.error("[%s] GitHub client is None! GITHUB_TOKEN likely not set in env.", self.role)
            return {"error": "GitHub client not configured. GITHUB_TOKEN env var is missing."}
        repo = inp["repo"]
        branch = inp.get("branch", "main")
        data = await self.github.get_file(repo, inp["path"], branch)
        return {"path": inp["path"], "content": data.get("decoded_content", "")}

    async def _tool_vercel_deploy(self, inp: dict[str, Any]) -> dict[str, Any]:
        if not self.vercel:
            logger.warning("[%s] Vercel client not configured — cannot deploy", self.role)
            return {"error": "Vercel client not configured. VERCEL_TOKEN env var is missing."}
        repo = inp["repo"]
        project_name = inp.get("project_name", "")
        framework = inp.get("framework", "nextjs")
        result = await self.vercel.deploy_repo(repo, project_name, framework)
        return result

    async def _tool_vercel_check_deploy(self, inp: dict[str, Any]) -> dict[str, Any]:
        if not self.vercel:
            logger.warning("[%s] Vercel client not configured", self.role)
            return {"error": "Vercel client not configured."}
        project_name = inp["project_name"]
        deployments = await self.vercel.get_deployments(project_name, limit=3)
        if not deployments:
            return {"status": "NO_DEPLOYMENTS", "project_name": project_name}

        latest = deployments[0]
        result: dict[str, Any] = {
            "project_name": project_name,
            "status": latest["state"],
            "url": latest.get("url", ""),
            "deployment_id": latest.get("id", ""),
        }

        # If failed, fetch build logs
        if latest["state"] == "ERROR":
            logs = await self.vercel.get_build_logs(latest["id"])
            result["build_logs"] = logs
            result["error_message"] = latest.get("error_message", "")

        return result

    async def _tool_github_merge_pr(self, inp: dict[str, Any]) -> dict[str, Any]:
        if not self.github:
            logger.warning("[%s] GitHub client not configured", self.role)
            return {"error": "GitHub client not configured."}
        repo = inp["repo"]
        pr_number = inp["pr_number"]
        method = inp.get("merge_method", "squash")
        result = await self.github.merge_pull_request(repo, pr_number, method)
        return {"success": True, "merged": True, "sha": result.get("sha", "")}

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

    async def _tool_discord_ask_user(self, inp: dict[str, Any]) -> dict[str, Any]:
        if not self._conversation_store or not self._thread_id:
            return {"status": "unavailable", "reply": None}

        import asyncio
        question = inp["question"]
        if inp.get("urgent"):
            question = f"🔴 **緊急** {question}"
        question = f"{question}\n\n@User 需要你的回覆"

        future = asyncio.get_event_loop().create_future()
        self._conversation_store.set_pending(
            self._thread_id, str(self.role), question, future,
        )
        await self.discord.agent_speak(
            thread_id=self._thread_id,
            agent_role=self.role,
            content=question,
            conversation_store=self._conversation_store,
        )

        timeout = 30 * 60  # 30 minutes default
        try:
            reply = await asyncio.wait_for(future, timeout=timeout)
            return {"status": "answered", "reply": reply}
        except asyncio.TimeoutError:
            self._conversation_store.clear_pending(self._thread_id, str(self.role))
            return {"status": "timeout", "reply": None}

    async def _tool_discord_discuss(self, inp: dict[str, Any]) -> dict[str, Any]:
        if not self._conversation_store or not self._thread_id:
            return {"status": "unavailable"}
        await self.discord.agent_speak(
            thread_id=self._thread_id,
            agent_role=self.role,
            content=inp["message"],
            conversation_store=self._conversation_store,
        )
        return {"status": "sent"}

    async def _tool_discord_report_blocker(self, inp: dict[str, Any]) -> dict[str, Any]:
        if not self._conversation_store or not self._thread_id:
            return {"status": "unavailable", "reply": None}

        import asyncio
        msg = f"⚠️ **Blocker**\n{inp['description']}\n\n@User 需要你的決定"
        future = asyncio.get_event_loop().create_future()
        self._conversation_store.set_pending(
            self._thread_id, str(self.role), msg, future,
        )
        await self.discord.agent_speak(
            thread_id=self._thread_id,
            agent_role=self.role,
            content=msg,
            conversation_store=self._conversation_store,
        )

        timeout = 30 * 60
        try:
            reply = await asyncio.wait_for(future, timeout=timeout)
            return {"status": "answered", "reply": reply}
        except asyncio.TimeoutError:
            self._conversation_store.clear_pending(self._thread_id, str(self.role))
            return {"status": "timeout", "reply": None}

    async def _tool_update_project_context(self, inp: dict[str, Any]) -> dict[str, Any]:
        if not self._project_context or not self._project_id:
            return {"status": "unavailable"}
        self._project_context.append(
            self._project_id,
            inp["category"],
            inp["content"],
        )
        return {"status": "recorded", "category": inp["category"]}

    async def _maybe_reflect(
        self, soul_manager: Any, task: AgentTask, result: dict[str, Any]
    ) -> None:
        """Use Haiku to decide if this run produced experience worth remembering."""
        import anthropic

        tokens = result.get("tokens_used", 0)
        success = "summary" in result and result["summary"]
        if tokens < 3000 and success:
            return  # Routine run, skip reflection

        client = anthropic.AsyncAnthropic(api_key=self.claude._client.api_key)
        try:
            response = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=256,
                system="判斷這次 agent 執行是否有值得長期記住的經驗。回答 JSON: {\"worth_saving\": bool, \"category\": \"技術經驗\"|\"協作模式\"|\"踩過的坑\"|\"偏好\", \"entry\": \"簡短描述\"}",
                messages=[{
                    "role": "user",
                    "content": f"Agent: {self.role}\n摘要: {result.get('summary', '')[:300]}\nTokens: {tokens}\n成功: {success}",
                }],
            )
            text = response.content[0].text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            data = json.loads(text)
            if data.get("worth_saving") and data.get("entry"):
                soul_manager.append(str(self.role), data["category"], data["entry"])
                logger.info("[%s] Soul updated: %s", self.role, data["entry"][:80])
        except Exception as e:
            logger.debug("Reflection skipped: %s", e)
        finally:
            await client.close()
