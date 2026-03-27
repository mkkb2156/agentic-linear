from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from services.gateway.discord.listener import ConversationListener


@pytest.fixture
def mock_deps() -> dict:
    from shared.conversation_store import ConversationStore
    return {
        "conversation_store": ConversationStore(data_dir=Path("/tmp/test_conv")),
        "intent_router": MagicMock(),
        "gatherer": MagicMock(),
        "dispatcher": MagicMock(),
        "linear_client": MagicMock(),
        "bot_user_id": 12345,
        "listen_channels": ["project-requests", "agent-war-room"],
    }


@pytest.fixture
def listener(mock_deps: dict) -> ConversationListener:
    return ConversationListener(**mock_deps)


class TestConversationListener:
    def test_should_ignore_bot_message(self, listener: ConversationListener) -> None:
        msg = MagicMock()
        msg.author.bot = True
        msg.webhook_id = None
        assert listener.should_ignore(msg) is True

    def test_should_not_ignore_user_message(self, listener: ConversationListener) -> None:
        msg = MagicMock()
        msg.author.bot = False
        msg.author.id = 99999
        msg.webhook_id = None
        assert listener.should_ignore(msg) is False

    def test_is_mention(self, listener: ConversationListener) -> None:
        msg = MagicMock()
        mention = MagicMock()
        mention.id = 12345
        msg.mentions = [mention]
        assert listener.is_mention(msg) is True

    def test_is_monitored_channel(self, listener: ConversationListener) -> None:
        msg = MagicMock()
        msg.channel.name = "project-requests"
        assert listener.is_monitored_channel(msg) is True

    def test_is_not_monitored_channel(self, listener: ConversationListener) -> None:
        msg = MagicMock()
        msg.channel.name = "random"
        assert listener.is_monitored_channel(msg) is False

    def test_is_webhook_message(self, listener: ConversationListener) -> None:
        msg = MagicMock()
        msg.webhook_id = 67890
        assert listener.is_webhook_message(msg) is True

    def test_is_in_bot_thread(self, listener: ConversationListener) -> None:
        listener._conversation_store.create_thread("t1", issue_id="ISS-1", project_id="proj-1")
        msg = MagicMock()
        type(msg.channel).id = PropertyMock(return_value="t1")
        msg.channel.type = MagicMock()
        msg.channel.type.name = "public_thread"
        assert listener.is_in_tracked_thread(msg) is True
