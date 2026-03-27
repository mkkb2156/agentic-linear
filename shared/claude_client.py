from __future__ import annotations

import asyncio
import logging
from typing import Any

import anthropic

from shared.models import AgentRole

logger = logging.getLogger(__name__)

# Agents that default to Opus for deeper reasoning
OPUS_DEFAULT_ROLES: set[AgentRole] = {AgentRole.SYSTEM_ARCHITECT}

MODEL_SONNET = "claude-sonnet-4-6"
MODEL_OPUS = "claude-opus-4-6"


class ClaudeClient:
    def __init__(self, api_key: str) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def close(self) -> None:
        await self._client.close()

    async def execute(
        self,
        agent_role: AgentRole,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        use_opus: bool = False,
        max_tokens: int = 16384,
    ) -> tuple[anthropic.types.Message, int, str]:
        """
        Execute a Claude API call with model routing.

        Returns (response, total_tokens_used, model_name).
        """
        model = MODEL_OPUS if (use_opus or agent_role in OPUS_DEFAULT_ROLES) else MODEL_SONNET

        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools

        response = await self._call_with_retry(**kwargs)

        tokens_used = response.usage.input_tokens + response.usage.output_tokens
        logger.info(
            "Claude %s call for %s: %d tokens",
            model,
            agent_role,
            tokens_used,
        )
        return response, tokens_used, model

    async def _call_with_retry(
        self, max_retries: int = 5, **kwargs: Any
    ) -> anthropic.types.Message:
        """Call Claude API with exponential backoff on 429/529."""
        for attempt in range(max_retries + 1):
            try:
                return await self._client.messages.create(**kwargs)
            except anthropic.RateLimitError:
                if attempt == max_retries:
                    raise
                wait = 2 ** (attempt + 1)
                logger.warning("Rate limited, retrying in %ds (attempt %d/%d)", wait, attempt + 1, max_retries)
                await asyncio.sleep(wait)
            except (anthropic.InternalServerError, anthropic.APIStatusError) as e:
                # Catch 529 Overloaded (OverloadedError inherits APIStatusError)
                if attempt == max_retries:
                    raise
                wait = min(2 ** (attempt + 1), 30)  # Cap at 30s
                logger.warning("API error (%s), retrying in %ds (attempt %d/%d)", type(e).__name__, wait, attempt + 1, max_retries)
                await asyncio.sleep(wait)
        raise RuntimeError("Unreachable")
