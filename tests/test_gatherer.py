from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.gateway.discord.gatherer import MultiTurnGatherer


@pytest.fixture
def gatherer() -> MultiTurnGatherer:
    from shared.conversation_store import ConversationStore
    store = ConversationStore(data_dir=Path("/tmp/test_conversations"))
    return MultiTurnGatherer(
        api_key="test-key",
        conversation_store=store,
    )


class TestMultiTurnGatherer:
    def test_initial_state(self, gatherer: MultiTurnGatherer) -> None:
        assert gatherer._conversation_store is not None

    @pytest.mark.asyncio
    async def test_start_gathering_creates_dm(self, gatherer: MultiTurnGatherer) -> None:
        with patch.object(gatherer, "_ask_haiku", new_callable=AsyncMock, return_value="ad-fast 主要面向什麼用戶？"):
            question = await gatherer.start_gathering("u1", "我想開發 ad-fast 廣告素材工具")

        dm = gatherer._conversation_store.get_dm("u1")
        assert dm is not None
        assert dm.state == "gathering"
        assert question is not None

    @pytest.mark.asyncio
    async def test_continue_gathering(self, gatherer: MultiTurnGatherer) -> None:
        gatherer._conversation_store.create_dm("u1")
        gatherer._conversation_store.update_dm_state("u1", "gathering")

        with patch.object(gatherer, "_ask_haiku", new_callable=AsyncMock, return_value="技術 stack 有偏好嗎？"):
            result = await gatherer.continue_gathering("u1", "B2B 電商賣家")

        assert result["type"] in ("question", "confirm")

    @pytest.mark.asyncio
    async def test_build_summary(self, gatherer: MultiTurnGatherer) -> None:
        gatherer._conversation_store.create_dm("u1")
        from shared.conversation_store import Message
        from datetime import datetime, timezone
        gatherer._conversation_store.append_dm_message("u1", Message(
            author_type="user", author_id="u1",
            content="我想開發 ad-fast", timestamp=datetime.now(timezone.utc),
        ))

        with patch.object(gatherer, "_ask_haiku", new_callable=AsyncMock, return_value='{"name":"ad-fast","users":"B2B","features":["圖片生成"],"stack":"Next.js+Supabase"}'):
            summary = await gatherer.build_summary("u1")

        assert "ad-fast" in str(summary)
