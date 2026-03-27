# tests/test_integration_conversational.py
"""Smoke test: verify all new components work together."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.conversation_store import ConversationStore, Message
from shared.soul_manager import SoulManager
from shared.project_context import ProjectContextManager


@pytest.fixture
def tmp_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def store(tmp_dir: Path) -> ConversationStore:
    return ConversationStore(data_dir=tmp_dir / "conversations")


@pytest.fixture
def soul(tmp_dir: Path) -> SoulManager:
    return SoulManager(souls_dir=tmp_dir / "souls")


@pytest.fixture
def project_ctx(tmp_dir: Path) -> ProjectContextManager:
    return ProjectContextManager(projects_dir=tmp_dir / "projects")


class TestEndToEndFlow:
    def test_full_conversation_lifecycle(
        self, store: ConversationStore, soul: SoulManager, project_ctx: ProjectContextManager
    ) -> None:
        """Simulate: user starts project → agents discuss in thread → memory updated."""

        # 1. Create thread for new project
        store.create_thread("thread-1", issue_id="DRO-42", project_id="proj-ad-fast")

        # 2. User message
        store.append_message("thread-1", Message(
            author_type="user", author_id="user-123",
            content="我想開發 ad-fast 廣告素材工具",
            timestamp=datetime.now(timezone.utc),
        ))

        # 3. Agent speaks
        store.append_message("thread-1", Message(
            author_type="agent", author_id="product_strategist",
            content="收到！PRD 分析中...",
            timestamp=datetime.now(timezone.utc),
        ))

        # 4. Agent asks user
        import asyncio
        loop = asyncio.new_event_loop()
        future = loop.create_future()
        store.set_pending("thread-1", "spec_architect", "需要支援影片嗎？", future)
        assert store.has_pending("thread-1")

        # 5. User replies → resolves pending
        store.resolve_pending("thread-1", "spec_architect", "先做圖片就好")
        assert future.result() == "先做圖片就好"
        assert not store.has_pending("thread-1", "spec_architect")

        # 6. Project context updated
        project_ctx.append("proj-ad-fast", "requirement", "B2B 電商賣家", project_name="ad-fast")
        project_ctx.append("proj-ad-fast", "constraint", "蝦皮 800x800", project_name="ad-fast")
        ctx = project_ctx.load("proj-ad-fast")
        assert "B2B" in ctx
        assert "800x800" in ctx

        # 7. Soul updated
        soul.append("frontend_engineer", "技術經驗", "Sharp 大圖處理要設 memory limit")
        soul_content = soul.load("frontend_engineer")
        assert "Sharp" in soul_content

        # 8. Context for next agent
        formatted = store.format_for_agent("thread-1")
        assert "ad-fast" in formatted
        assert "product_strategist" in formatted

        # 9. Verify participants tracked
        thread = store.get_thread("thread-1")
        assert "user-123" in thread.participants
        assert "product_strategist" in thread.participants
