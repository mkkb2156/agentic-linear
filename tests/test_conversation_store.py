from __future__ import annotations

import asyncio
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from shared.conversation_store import (
    ConversationStore,
    DMContext,
    Message,
    PendingQuestion,
    ThreadContext,
)


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    d = tmp_path / "conversations"
    d.mkdir()
    return d


@pytest.fixture
def store(tmp_data_dir: Path) -> ConversationStore:
    return ConversationStore(data_dir=tmp_data_dir)


def _msg(author_id: str = "user1", content: str = "hello", author_type: str = "user") -> Message:
    return Message(
        author_type=author_type,
        author_id=author_id,
        content=content,
        timestamp=datetime.now(timezone.utc),
    )


class TestThreadContext:
    def test_create_thread(self, store: ConversationStore) -> None:
        store.create_thread("t1", issue_id="ISS-1", project_id="proj-1")
        ctx = store.get_thread("t1")
        assert ctx is not None
        assert ctx.issue_id == "ISS-1"
        assert ctx.project_id == "proj-1"
        assert ctx.messages == []

    def test_append_message(self, store: ConversationStore) -> None:
        store.create_thread("t1", issue_id="ISS-1", project_id="proj-1")
        msg = _msg()
        store.append_message("t1", msg)
        ctx = store.get_thread("t1")
        assert len(ctx.messages) == 1
        assert ctx.messages[0].content == "hello"
        assert "user1" in ctx.participants

    def test_append_to_missing_thread_raises(self, store: ConversationStore) -> None:
        with pytest.raises(KeyError):
            store.append_message("missing", _msg())

    def test_get_recent_messages(self, store: ConversationStore) -> None:
        store.create_thread("t1", issue_id="ISS-1", project_id="proj-1")
        for i in range(60):
            store.append_message("t1", _msg(content=f"msg-{i}"))
        recent = store.get_recent_messages("t1", limit=50)
        assert len(recent) == 50
        assert recent[0].content == "msg-10"
        assert recent[-1].content == "msg-59"


class TestDMContext:
    def test_create_dm(self, store: ConversationStore) -> None:
        store.create_dm("u1")
        dm = store.get_dm("u1")
        assert dm is not None
        assert dm.state == "idle"

    def test_append_dm_message(self, store: ConversationStore) -> None:
        store.create_dm("u1")
        store.append_dm_message("u1", _msg())
        dm = store.get_dm("u1")
        assert len(dm.messages) == 1

    def test_update_dm_state(self, store: ConversationStore) -> None:
        store.create_dm("u1")
        store.update_dm_state("u1", "gathering")
        assert store.get_dm("u1").state == "gathering"


class TestPendingQuestions:
    def test_set_and_check_pending(self, store: ConversationStore) -> None:
        store.create_thread("t1", issue_id="ISS-1", project_id="proj-1")
        loop = asyncio.new_event_loop()
        future = loop.create_future()
        store.set_pending("t1", "qa_engineer", "Need clarification?", future)
        assert store.has_pending("t1", "qa_engineer")

    def test_resolve_pending(self, store: ConversationStore) -> None:
        store.create_thread("t1", issue_id="ISS-1", project_id="proj-1")
        loop = asyncio.new_event_loop()
        future = loop.create_future()
        store.set_pending("t1", "qa_engineer", "Need clarification?", future)
        store.resolve_pending("t1", "qa_engineer", "Yes, do it")
        assert future.result() == "Yes, do it"
        assert not store.has_pending("t1", "qa_engineer")


class TestPersistence:
    def test_persist_and_reload(self, tmp_data_dir: Path) -> None:
        store1 = ConversationStore(data_dir=tmp_data_dir)
        store1.create_thread("t1", issue_id="ISS-1", project_id="proj-1")
        store1.append_message("t1", _msg(content="persisted"))

        store2 = ConversationStore(data_dir=tmp_data_dir)
        store2.load()
        ctx = store2.get_thread("t1")
        assert ctx is not None
        assert len(ctx.messages) == 1
        assert ctx.messages[0].content == "persisted"
