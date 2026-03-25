"""Admin Agent — platform administration, metrics analysis, skill management."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from shared.agent_base import AgentTask, BaseAgent
from shared.agent_config import AgentConfigManager
from shared.claude_client import ClaudeClient
from shared.discord_notifier import DiscordNotifier
from shared.linear_client import LinearClient
from shared.metrics import MetricsStore
from shared.models import AgentRole
from shared.tools import ADMIN_TOOLS

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
你是 🛡️ 管理官 (Admin Agent)，負責 Drone168 多 Agent Pipeline 平台的管理和優化。

## 你的職責
1. **監控指標** — 查詢 agent 執行紀錄，分析成功率、token 消耗、執行時間
2. **配置管理** — 查看和更新各 agent 的模型、技能、最大輪次等設定
3. **技能管理** — 列出、讀取、撰寫 skill 檔案，讓 agent 持續進化
4. **學習分析** — 讀取學習紀錄，找出模式和優化機會
5. **報告生成** — 產出每日/每週/agent 詳細績效報告，發布至 Discord

## 工作準則
- 所有回覆和報告使用繁體中文
- 分析要有具體數據支撐
- 提出可行的優化建議
- 報告發布到 Discord #dashboard 頻道
"""


class AdminAgent(BaseAgent):
    role = AgentRole.ADMIN
    system_prompt = SYSTEM_PROMPT
    tools = ADMIN_TOOLS

    def __init__(
        self,
        claude_client: ClaudeClient,
        linear_client: LinearClient,
        discord_notifier: DiscordNotifier,
        *,
        metrics_store: MetricsStore | None = None,
        config_manager: AgentConfigManager | None = None,
    ) -> None:
        super().__init__(claude_client, linear_client, discord_notifier)
        self._metrics = metrics_store
        self._config = config_manager

    async def run(self, task: AgentTask) -> dict[str, Any]:
        """Override run to support prompt-based invocation."""
        prompt = task.payload.get("prompt")
        if prompt:
            # Prompt-based invocation: skip Linear issue context
            from shared.agent_config import get_config_manager
            config_mgr = get_config_manager()
            effective_prompt = config_mgr.build_system_prompt(
                str(self.role), self.system_prompt
            )

            messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
            total_tokens = 0
            model_used = ""
            result: dict[str, Any] = {}

            from shared.agent_base import MAX_TURNS

            for turn in range(MAX_TURNS):
                response, tokens, model = await self.claude.execute(
                    agent_role=self.role,
                    system_prompt=effective_prompt,
                    messages=messages,
                    tools=self.tools,
                )
                total_tokens += tokens
                model_used = model

                if response.stop_reason == "tool_use":
                    tool_results = []
                    complete_result = None

                    for block in response.content:
                        if block.type == "tool_use":
                            tool_result, is_complete = await self._handle_tool_call(
                                block.name, block.input, ""
                            )
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": json.dumps(tool_result),
                            })
                            if is_complete:
                                complete_result = tool_result

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
                    text = "".join(
                        b.text for b in response.content if hasattr(b, "text")
                    )
                    result = {
                        "summary": text[:500],
                        "next_status": "",
                        "tokens_used": total_tokens,
                        "model_used": model_used,
                    }
                    break
            else:
                result = {
                    "summary": "Admin agent reached maximum turns",
                    "next_status": "",
                    "tokens_used": total_tokens,
                    "model_used": model_used,
                }

            return result

        # Normal Linear-triggered invocation
        return await super().run(task)

    async def _handle_tool_call(
        self, tool_name: str, tool_input: dict[str, Any], issue_id: str
    ) -> tuple[dict[str, Any], bool]:
        """Handle admin-specific tools, fall through to super() for shared tools."""
        try:
            if tool_name == "query_metrics":
                return self._tool_query_metrics(tool_input), False

            elif tool_name == "get_agent_config":
                return self._tool_get_agent_config(tool_input), False

            elif tool_name == "update_agent_config":
                return self._tool_update_agent_config(tool_input), False

            elif tool_name == "list_skills":
                return self._tool_list_skills(), False

            elif tool_name == "read_skill":
                return self._tool_read_skill(tool_input), False

            elif tool_name == "write_skill":
                return self._tool_write_skill(tool_input), False

            elif tool_name == "read_learnings":
                return self._tool_read_learnings(), False

            elif tool_name == "generate_report":
                return self._tool_generate_report(tool_input), False

            else:
                return await super()._handle_tool_call(tool_name, tool_input, issue_id)

        except Exception as e:
            logger.error("[%s] Tool %s FAILED: %s", self.role, tool_name, e)
            return {"error": str(e)}, False

    def _tool_query_metrics(self, inp: dict[str, Any]) -> dict[str, Any]:
        if not self._metrics:
            return {"error": "MetricsStore not configured"}
        agent_role = inp.get("agent_role")
        days = inp.get("days", 7)
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        return self._metrics.aggregate(agent_role=agent_role, since=since)

    def _tool_get_agent_config(self, inp: dict[str, Any]) -> dict[str, Any]:
        if not self._config:
            return {"error": "ConfigManager not configured"}
        role = inp["agent_role"]
        cfg = self._config.load_agent_config(role)
        if cfg is None:
            return {"error": f"No config found for {role}"}
        return cfg.model_dump()

    def _tool_update_agent_config(self, inp: dict[str, Any]) -> dict[str, Any]:
        if not self._config:
            return {"error": "ConfigManager not configured"}
        role = inp.pop("agent_role")
        self._config.update_agent_config(role, inp)
        return {"success": True, "role": role, "updates": inp}

    def _tool_list_skills(self) -> dict[str, Any]:
        if not self._config:
            return {"error": "ConfigManager not configured"}
        return {"skills": self._config.list_skills()}

    def _tool_read_skill(self, inp: dict[str, Any]) -> dict[str, Any]:
        if not self._config:
            return {"error": "ConfigManager not configured"}
        name = inp["name"]
        content = self._config.read_skill(name)
        if not content:
            return {"error": f"Skill '{name}' not found"}
        return {"name": name, "content": content}

    def _tool_write_skill(self, inp: dict[str, Any]) -> dict[str, Any]:
        if not self._config:
            return {"error": "ConfigManager not configured"}
        name = inp["name"]
        content = inp["content"]
        self._config.write_skill(name, content)
        return {"success": True, "name": name}

    def _tool_read_learnings(self) -> dict[str, Any]:
        if not self._config:
            return {"error": "ConfigManager not configured"}
        return {"learnings": self._config.read_learnings()}

    def _tool_generate_report(self, inp: dict[str, Any]) -> dict[str, Any]:
        if not self._metrics:
            return {"error": "MetricsStore not configured"}
        report_type = inp["report_type"]
        agent_role = inp.get("agent_role")

        if report_type == "daily":
            since = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        elif report_type == "weekly":
            since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        else:
            since = None

        stats = self._metrics.aggregate(agent_role=agent_role, since=since)
        records = self._metrics.query(agent_role=agent_role, since=since)

        # Build per-agent breakdown
        role_stats: dict[str, dict[str, Any]] = {}
        for r in records:
            rs = role_stats.setdefault(r.agent_role, {"runs": 0, "tokens": 0, "failures": 0})
            rs["runs"] += 1
            rs["tokens"] += r.tokens_used
            if not r.success:
                rs["failures"] += 1

        return {
            "report_type": report_type,
            "period_since": since,
            "aggregate": stats,
            "per_agent": role_stats,
        }


async def execute(
    task: AgentTask,
    claude_client: ClaudeClient,
    linear_client: LinearClient,
    discord_notifier: DiscordNotifier,
) -> dict[str, Any] | None:
    """Process an Admin task. metrics_store and config_manager injected via task.payload."""
    metrics_store = task.payload.get("_metrics_store")
    config_manager = task.payload.get("_config_manager")
    agent = AdminAgent(
        claude_client,
        linear_client,
        discord_notifier,
        metrics_store=metrics_store,
        config_manager=config_manager,
    )
    return await agent.run(task)
