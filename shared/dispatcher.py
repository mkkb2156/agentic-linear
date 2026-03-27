"""Agent dispatcher — runs agents as background asyncio tasks.

Replaces the PostgreSQL task queue. Linear is the source of truth for task state;
the dispatcher just executes agents when triggered by webhook events.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from shared.agent_base import AgentTask
from shared.claude_client import ClaudeClient
from shared.discord_notifier import DiscordNotifier
from shared.linear_client import LinearClient
from shared.models import AgentRole

logger = logging.getLogger(__name__)

# Type for agent handler functions
AgentHandler = Callable[
    ...,
    Awaitable[dict[str, Any] | None],
]

# In-memory idempotency cache (delivery_id:agent_role → timestamp)
# Entries expire after 1 hour
_IDEMPOTENCY_TTL = 3600
_seen_keys: dict[str, float] = {}


def _check_idempotency(key: str) -> bool:
    """Return True if this key has been seen recently (duplicate)."""
    now = time.monotonic()

    # Lazy cleanup: remove expired entries
    expired = [k for k, ts in _seen_keys.items() if now - ts > _IDEMPOTENCY_TTL]
    for k in expired:
        del _seen_keys[k]

    if key in _seen_keys:
        return True  # Duplicate

    _seen_keys[key] = now
    return False


class AgentDispatcher:
    """
    Dispatches agents as background asyncio tasks.

    Usage:
        dispatcher = AgentDispatcher(claude, linear, discord)
        dispatcher.register(AgentRole.PRODUCT_STRATEGIST, product_strategist_execute)
        await dispatcher.dispatch(AgentRole.SPEC_ARCHITECT, task, delivery_id="abc")
    """

    def __init__(
        self,
        claude_client: ClaudeClient,
        linear_client: LinearClient,
        discord_notifier: DiscordNotifier,
        metrics_store: Any | None = None,
        config_manager: Any | None = None,
        github_client: Any | None = None,
        vercel_client: Any | None = None,
    ) -> None:
        self._claude = claude_client
        self._linear = linear_client
        self._discord = discord_notifier
        self._metrics_store = metrics_store
        self._config_manager = config_manager
        self._github = github_client
        self._vercel = vercel_client
        self._conversation_store = None  # Set externally
        self._soul_manager = None  # Set externally
        self._project_context = None  # Set externally
        self._dream_consolidator = None  # Set externally
        self._registry: dict[AgentRole, AgentHandler] = {}
        self._active_tasks: set[asyncio.Task[Any]] = set()

    def register(self, role: AgentRole, handler: AgentHandler) -> None:
        """Register an agent handler for a role."""
        self._registry[role] = handler

    def register_all(self, registry: dict[str, AgentHandler]) -> None:
        """Register multiple handlers from a {role_str: handler} dict."""
        for role_str, handler in registry.items():
            self._registry[AgentRole(role_str)] = handler

    def set_memory_components(
        self,
        conversation_store: Any = None,
        soul_manager: Any = None,
        project_context: Any = None,
        dream_consolidator: Any = None,
    ) -> None:
        self._conversation_store = conversation_store
        self._soul_manager = soul_manager
        self._project_context = project_context
        self._dream_consolidator = dream_consolidator

    async def dispatch(
        self,
        agent_role: AgentRole,
        task: AgentTask,
        delivery_id: str | None = None,
    ) -> bool:
        """
        Dispatch an agent to run in the background.
        Returns True if dispatched, False if duplicate or unknown role.
        """
        handler = self._registry.get(agent_role)
        if not handler:
            logger.error("No handler registered for agent role: %s", agent_role)
            return False

        # Idempotency check
        if delivery_id:
            idem_key = f"{delivery_id}:{agent_role}"
            if _check_idempotency(idem_key):
                logger.info("Duplicate dispatch skipped: %s", idem_key)
                return False

        # Launch as background task
        bg_task = asyncio.create_task(
            self._run_agent(agent_role, handler, task),
            name=f"agent:{agent_role}:{task.issue_id}",
        )
        self._active_tasks.add(bg_task)
        bg_task.add_done_callback(self._active_tasks.discard)

        logger.info(
            "Dispatched %s for issue %s (active tasks: %d)",
            agent_role,
            task.issue_id,
            len(self._active_tasks),
        )
        return True

    async def _run_agent(
        self,
        agent_role: AgentRole,
        handler: AgentHandler,
        task: AgentTask,
    ) -> None:
        """Run an agent handler with error handling and Discord alerting."""
        success = False
        error_msg = ""
        result: dict[str, Any] = {}
        start_time = time.monotonic()
        try:
            # Inject memory context into agent via task payload
            task.payload["_conversation_store"] = self._conversation_store
            task.payload["_project_context"] = self._project_context
            task.payload["_soul_manager"] = self._soul_manager
            result = await handler(
                task, self._claude, self._linear, self._discord,
                github_client=self._github,
                vercel_client=self._vercel,
            ) or {}
            tokens = result.get("tokens_used", 0)
            model = result.get("model_used", "")
            logger.info(
                "Agent %s completed for %s: %d tokens (%s)",
                agent_role,
                task.issue_id,
                tokens,
                model,
            )
            success = True
        except Exception as e:
            error_msg = str(e)
            logger.exception("Agent %s failed for %s: %s", agent_role, task.issue_id, e)
            await self._discord.send_alert(
                agent_role=agent_role,
                title=f"Agent Failed: {task.issue_id}",
                description=f"Agent `{agent_role}` failed.\nError: {e}",
            )
        finally:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            tokens = (result or {}).get("tokens_used", 0)
            model = (result or {}).get("model_used", "")
            summary_text = (result or {}).get("summary", "")

            if self._metrics_store:
                from shared.metrics import AgentRunRecord
                self._metrics_store.record(AgentRunRecord(
                    agent_role=str(agent_role),
                    issue_id=task.issue_id,
                    tokens_used=tokens,
                    model_used=model,
                    duration_ms=duration_ms,
                    success=success,
                    error_message=error_msg,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    summary=summary_text[:200],
                ))

            # Learning capture: record noteworthy events
            if self._config_manager and (not success or tokens > 5000):
                tag = "FAIL" if not success else "HIGH_TOKEN"
                self._config_manager.append_learning(
                    f"{agent_role} | {task.issue_id} | {tag} | {tokens} tokens | {summary_text[:100]}"
                )

            # Trigger dream consolidation if thresholds met
            project_id = task.payload.get("project_id", "")
            await self._maybe_dream(str(agent_role), project_id)

            # Auto-trigger learning review every 10 runs
            if (self._metrics_store
                and self._metrics_store.run_count % 10 == 0
                and self._metrics_store.run_count > 0):
                from shared.models import AgentRole as AR
                admin_handler = self._registry.get(AR.ADMIN)
                if admin_handler:
                    from shared.agent_base import AgentTask as AT
                    learn_task = AT(
                        issue_id=f"learn-{self._metrics_store.run_count}",
                        agent_role="admin",
                        payload={"prompt": "檢視學習紀錄和 metrics，分析模式和優化機會，必要時更新 skill 文件。將分析報告發布到 Discord #dashboard。"},
                    )
                    asyncio.create_task(
                        self._run_agent(AR.ADMIN, admin_handler, learn_task),
                        name=f"admin:learn:{self._metrics_store.run_count}",
                    )

    async def _maybe_dream(self, agent_role: str, project_id: str = "") -> None:
        if not self._metrics_store or not self._dream_consolidator:
            return

        from shared.config import get_settings
        settings = get_settings()

        soul_count = self._metrics_store.increment_dream_counter(f"soul:{agent_role}")
        if soul_count >= settings.dream_soul_threshold:
            asyncio.create_task(self._dream_consolidator.dream_soul(agent_role))
            self._metrics_store.reset_dream_counter(f"soul:{agent_role}")
            logger.info("Dream triggered for agent soul: %s", agent_role)

        if project_id:
            proj_count = self._metrics_store.increment_dream_counter(f"project:{project_id}")
            if proj_count >= settings.dream_project_threshold:
                asyncio.create_task(self._dream_consolidator.dream_project(project_id))
                self._metrics_store.reset_dream_counter(f"project:{project_id}")
                logger.info("Dream triggered for project: %s", project_id)

    async def shutdown(self) -> None:
        """Wait for all active agent tasks to complete."""
        if self._active_tasks:
            logger.info("Waiting for %d active agent tasks...", len(self._active_tasks))
            await asyncio.gather(*self._active_tasks, return_exceptions=True)
        logger.info("Dispatcher shut down")

    @property
    def active_count(self) -> int:
        return len(self._active_tasks)
