from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.gateway.discord.intent_router import IntentResult, IntentRouter


@pytest.fixture
def router() -> IntentRouter:
    return IntentRouter(api_key="test-key")


class TestIntentResult:
    def test_parse_new_project(self) -> None:
        result = IntentResult(
            intent="new_project",
            confidence=0.95,
            summary="User wants to build ad-fast",
        )
        assert result.intent == "new_project"

    def test_parse_with_target(self) -> None:
        result = IntentResult(
            intent="agent_command",
            confidence=0.9,
            target_agent="frontend_engineer",
            summary="Redeploy request",
        )
        assert result.target_agent == "frontend_engineer"


class TestIntentRouter:
    @pytest.mark.asyncio
    async def test_classify_returns_intent(self, router: IntentRouter) -> None:
        mock_response = MagicMock()
        mock_response.content = [MagicMock(
            text='{"intent":"new_project","confidence":0.95,"target_agent":null,"target_issue":null,"summary":"Build ad-fast"}'
        )]

        with patch.object(router, "_client", create=True) as mock_client:
            mock_client.messages = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            result = await router.classify("我想開發 ad-fast", "project-requests")

        assert result.intent == "new_project"
        assert result.confidence >= 0.9
