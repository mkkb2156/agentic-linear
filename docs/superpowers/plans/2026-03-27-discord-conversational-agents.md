# Discord Conversational Agents — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the Discord bot from slash-command-only to a natural conversational multi-agent collaboration system where agents read messages, ask questions, discuss with each other, and maintain persistent memory.

**Architecture:** Add a message listener layer on top of the existing bot, with an intent router (Haiku) that classifies messages and routes them to handlers. Agents communicate via Discord webhooks with unique personas, coordinated through an in-memory ConversationStore. Two-layer memory (Agent Soul + Project Context) with Auto-Dream consolidation.

**Tech Stack:** Python 3.12, discord.py, Anthropic SDK (Haiku for routing, Sonnet for dreams), Pydantic, asyncio Futures for agent await mechanism.

---

## File Structure

### New files

| File | Responsibility |
|------|---------------|
| `shared/conversation_store.py` | In-memory + JSONL conversation state per thread/DM |
| `shared/soul_manager.py` | Agent soul (cross-project memory) read/write/reflect |
| `shared/project_context.py` | Project-specific memory read/write |
| `shared/dream.py` | Auto-Dream consolidation via direct Anthropic SDK |
| `gateway/discord/listener.py` | Message monitoring + routing to intent router |
| `gateway/discord/intent_router.py` | Haiku-based intent classification |
| `gateway/discord/gatherer.py` | Multi-turn requirement gathering (DM + channel) |
| `tests/test_conversation_store.py` | ConversationStore tests |
| `tests/test_soul_manager.py` | SoulManager tests |
| `tests/test_project_context.py` | ProjectContextManager tests |
| `tests/test_dream.py` | DreamConsolidator tests |
| `tests/test_intent_router.py` | IntentRouter tests |
| `tests/test_listener.py` | ConversationListener tests |
| `tests/test_gatherer.py` | MultiTurnGatherer tests |

### Modified files

| File | Changes |
|------|---------|
| `shared/config.py` | Add `listen_channels`, `agent_ask_timeout_minutes`, `dream_soul_threshold`, `dream_project_threshold` |
| `shared/models.py` | Add `AGENT_PERSONAS` dict with `username` field |
| `shared/tools.py` | Add 4 new tools: `discord_ask_user`, `discord_discuss`, `discord_report_blocker`, `update_project_context` |
| `shared/agent_base.py` | Add tool handlers for new tools + await mechanism |
| `shared/agent_config.py` | Extend `build_system_prompt` to inject soul + project context |
| `shared/discord_notifier.py` | Add `agent_speak` method for thread messages with persona |
| `shared/dispatcher.py` | Add `_maybe_dream` trigger + pass `thread_id`/`project_id` |
| `shared/metrics.py` | Add `count_since_last_dream` + `reset_dream_counter` |
| `gateway/discord/bot.py` | Enable `message_content` intent, wire `on_message` to listener |
| `gateway/main.py` | Initialize ConversationStore, SoulManager, ProjectContextManager, DreamConsolidator |

---

## Task 1: ConversationStore

**Files:**
- Create: `shared/conversation_store.py`
- Test: `tests/test_conversation_store.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_conversation_store.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_conversation_store.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'shared.conversation_store'`

- [ ] **Step 3: Implement ConversationStore**

```python
# shared/conversation_store.py
"""In-memory conversation state with JSONL persistence for crash recovery.

Stores thread contexts (per Linear issue) and DM sessions (per user).
Agents read from here to get Discord conversation history.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "conversations"


@dataclass
class Message:
    author_type: Literal["user", "agent", "bot"]
    author_id: str
    content: str
    timestamp: datetime
    reply_to: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "author_type": self.author_type,
            "author_id": self.author_id,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "reply_to": self.reply_to,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Message:
        return cls(
            author_type=d["author_type"],
            author_id=d["author_id"],
            content=d["content"],
            timestamp=datetime.fromisoformat(d["timestamp"]),
            reply_to=d.get("reply_to"),
            metadata=d.get("metadata", {}),
        )


@dataclass
class PendingQuestion:
    agent_role: str
    question: str
    asked_at: datetime
    timeout_minutes: int = 30
    callback: asyncio.Future | None = None


@dataclass
class ThreadContext:
    thread_id: str
    issue_id: str
    project_id: str
    messages: list[Message] = field(default_factory=list)
    participants: set[str] = field(default_factory=set)
    pending_questions: dict[str, PendingQuestion] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DMContext:
    user_id: str
    messages: list[Message] = field(default_factory=list)
    state: Literal["idle", "gathering", "confirming", "confirmed"] = "idle"
    draft_project: dict[str, Any] = field(default_factory=dict)


class ConversationStore:
    def __init__(self, data_dir: Path | None = None) -> None:
        self._data_dir = data_dir or DATA_DIR
        self._threads: dict[str, ThreadContext] = {}
        self._dms: dict[str, DMContext] = {}

    # ---- Thread operations ----

    def create_thread(self, thread_id: str, *, issue_id: str, project_id: str) -> ThreadContext:
        ctx = ThreadContext(thread_id=thread_id, issue_id=issue_id, project_id=project_id)
        self._threads[thread_id] = ctx
        return ctx

    def get_thread(self, thread_id: str) -> ThreadContext | None:
        return self._threads.get(thread_id)

    def get_thread_by_issue(self, issue_id: str) -> ThreadContext | None:
        for ctx in self._threads.values():
            if ctx.issue_id == issue_id:
                return ctx
        return None

    def append_message(self, thread_id: str, msg: Message) -> None:
        ctx = self._threads.get(thread_id)
        if ctx is None:
            raise KeyError(f"Thread {thread_id} not found")
        ctx.messages.append(msg)
        ctx.participants.add(msg.author_id)
        ctx.updated_at = datetime.now(timezone.utc)
        self._persist_message(thread_id, msg)

    def get_recent_messages(self, thread_id: str, limit: int = 50) -> list[Message]:
        ctx = self._threads.get(thread_id)
        if ctx is None:
            return []
        return ctx.messages[-limit:]

    # ---- DM operations ----

    def create_dm(self, user_id: str) -> DMContext:
        dm = DMContext(user_id=user_id)
        self._dms[user_id] = dm
        return dm

    def get_dm(self, user_id: str) -> DMContext | None:
        return self._dms.get(user_id)

    def append_dm_message(self, user_id: str, msg: Message) -> None:
        dm = self._dms.get(user_id)
        if dm is None:
            raise KeyError(f"DM session {user_id} not found")
        dm.messages.append(msg)

    def update_dm_state(
        self, user_id: str, state: Literal["idle", "gathering", "confirming", "confirmed"]
    ) -> None:
        dm = self._dms.get(user_id)
        if dm is None:
            raise KeyError(f"DM session {user_id} not found")
        dm.state = state

    # ---- Pending questions ----

    def set_pending(
        self,
        thread_id: str,
        agent_role: str,
        question: str,
        future: asyncio.Future,
        timeout_minutes: int = 30,
    ) -> None:
        ctx = self._threads.get(thread_id)
        if ctx is None:
            raise KeyError(f"Thread {thread_id} not found")
        ctx.pending_questions[agent_role] = PendingQuestion(
            agent_role=agent_role,
            question=question,
            asked_at=datetime.now(timezone.utc),
            timeout_minutes=timeout_minutes,
            callback=future,
        )

    def has_pending(self, thread_id: str, agent_role: str | None = None) -> bool:
        ctx = self._threads.get(thread_id)
        if ctx is None:
            return False
        if agent_role:
            return agent_role in ctx.pending_questions
        return len(ctx.pending_questions) > 0

    def resolve_pending(self, thread_id: str, agent_role: str, reply: str) -> bool:
        ctx = self._threads.get(thread_id)
        if ctx is None or agent_role not in ctx.pending_questions:
            return False
        pq = ctx.pending_questions.pop(agent_role)
        if pq.callback and not pq.callback.done():
            pq.callback.set_result(reply)
        return True

    def resolve_any_pending(self, thread_id: str, reply: str) -> bool:
        ctx = self._threads.get(thread_id)
        if ctx is None or not ctx.pending_questions:
            return False
        agent_role = next(iter(ctx.pending_questions))
        return self.resolve_pending(thread_id, agent_role, reply)

    def clear_pending(self, thread_id: str, agent_role: str) -> None:
        ctx = self._threads.get(thread_id)
        if ctx and agent_role in ctx.pending_questions:
            pq = ctx.pending_questions.pop(agent_role)
            if pq.callback and not pq.callback.done():
                pq.callback.cancel()

    # ---- Persistence ----

    def _persist_message(self, thread_id: str, msg: Message) -> None:
        self._data_dir.mkdir(parents=True, exist_ok=True)
        path = self._data_dir / f"{thread_id}.jsonl"
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(msg.to_dict(), ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error("Failed to persist message: %s", e)

    def load(self) -> None:
        if not self._data_dir.exists():
            return
        for path in self._data_dir.glob("*.jsonl"):
            thread_id = path.stem
            if thread_id not in self._threads:
                # Rebuild with placeholder IDs — metadata is in the messages
                self._threads[thread_id] = ThreadContext(
                    thread_id=thread_id, issue_id="", project_id=""
                )
            try:
                with open(path, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        msg = Message.from_dict(json.loads(line))
                        ctx = self._threads[thread_id]
                        ctx.messages.append(msg)
                        ctx.participants.add(msg.author_id)
                # Restore issue_id/project_id from first message metadata if available
                ctx = self._threads[thread_id]
                if ctx.messages and ctx.messages[0].metadata:
                    ctx.issue_id = ctx.messages[0].metadata.get("issue_id", "")
                    ctx.project_id = ctx.messages[0].metadata.get("project_id", "")
            except Exception as e:
                logger.error("Failed to load conversation %s: %s", path, e)

    # ---- Context building for agents ----

    def format_for_agent(self, thread_id: str, limit: int = 50) -> str:
        messages = self.get_recent_messages(thread_id, limit=limit)
        lines = []
        for msg in messages:
            prefix = msg.author_id
            lines.append(f"{prefix}: {msg.content}")
        return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_conversation_store.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add shared/conversation_store.py tests/test_conversation_store.py
git commit -m "feat: add ConversationStore with JSONL persistence"
```

---

## Task 2: SoulManager

**Files:**
- Create: `shared/soul_manager.py`
- Test: `tests/test_soul_manager.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_soul_manager.py
from __future__ import annotations

from pathlib import Path

import pytest

from shared.soul_manager import SoulManager


@pytest.fixture
def tmp_souls_dir(tmp_path: Path) -> Path:
    d = tmp_path / "souls"
    d.mkdir()
    return d


@pytest.fixture
def manager(tmp_souls_dir: Path) -> SoulManager:
    return SoulManager(souls_dir=tmp_souls_dir)


class TestSoulManager:
    def test_load_empty(self, manager: SoulManager) -> None:
        assert manager.load("frontend_engineer") == ""

    def test_append_and_load(self, manager: SoulManager) -> None:
        manager.append("frontend_engineer", "技術經驗", "Sharp 處理大圖要設 limit")
        content = manager.load("frontend_engineer")
        assert "Sharp" in content
        assert "技術經驗" in content

    def test_append_multiple_categories(self, manager: SoulManager) -> None:
        manager.append("backend_engineer", "技術經驗", "Supabase RLS 注意事項")
        manager.append("backend_engineer", "踩過的坑", "Storage 5MB 限制")
        content = manager.load("backend_engineer")
        assert "Supabase RLS" in content
        assert "Storage 5MB" in content

    def test_write_replaces_content(self, manager: SoulManager) -> None:
        manager.append("qa_engineer", "技術經驗", "old entry")
        manager.write("qa_engineer", "# 🧪 QA Engineer — Soul\n\n## 技術經驗\n- new entry only")
        content = manager.load("qa_engineer")
        assert "new entry only" in content
        assert "old entry" not in content

    def test_line_count(self, manager: SoulManager) -> None:
        manager.write("devops", "\n".join([f"- line {i}" for i in range(120)]))
        assert manager.line_count("devops") == 120
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_soul_manager.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement SoulManager**

```python
# shared/soul_manager.py
"""Agent Soul — persistent cross-project memory per agent.

Each agent has a soul file (markdown) that records technical experience,
collaboration patterns, past mistakes, and preferences.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

SOULS_DIR = Path(__file__).resolve().parent / "agent_config" / "souls"


class SoulManager:
    def __init__(self, souls_dir: Path | None = None) -> None:
        self._dir = souls_dir or SOULS_DIR

    def load(self, role: str) -> str:
        path = self._dir / f"{role}.md"
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8").strip()

    def write(self, role: str, content: str) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        path = self._dir / f"{role}.md"
        path.write_text(content, encoding="utf-8")
        logger.info("Soul updated: %s", path)

    def append(self, role: str, category: str, entry: str) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        path = self._dir / f"{role}.md"
        today = date.today().isoformat()
        tagged_entry = f"- [{today}] {entry}"

        if not path.exists():
            content = f"# {role} — Soul\n\n## {category}\n{tagged_entry}\n"
            path.write_text(content, encoding="utf-8")
            return

        content = path.read_text(encoding="utf-8")
        section_header = f"## {category}"
        if section_header in content:
            # Append under existing section
            idx = content.index(section_header) + len(section_header)
            # Find end of header line
            newline_idx = content.index("\n", idx)
            content = content[:newline_idx + 1] + tagged_entry + "\n" + content[newline_idx + 1:]
        else:
            # Add new section at end
            content = content.rstrip() + f"\n\n{section_header}\n{tagged_entry}\n"

        path.write_text(content, encoding="utf-8")

    def line_count(self, role: str) -> int:
        content = self.load(role)
        if not content:
            return 0
        return len(content.split("\n"))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_soul_manager.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add shared/soul_manager.py tests/test_soul_manager.py
git commit -m "feat: add SoulManager for agent cross-project memory"
```

---

## Task 3: ProjectContextManager

**Files:**
- Create: `shared/project_context.py`
- Test: `tests/test_project_context.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_project_context.py
from __future__ import annotations

from pathlib import Path

import pytest

from shared.project_context import ProjectContextManager


@pytest.fixture
def tmp_projects_dir(tmp_path: Path) -> Path:
    d = tmp_path / "projects"
    d.mkdir()
    return d


@pytest.fixture
def manager(tmp_projects_dir: Path) -> ProjectContextManager:
    return ProjectContextManager(projects_dir=tmp_projects_dir)


class TestProjectContextManager:
    def test_load_empty(self, manager: ProjectContextManager) -> None:
        assert manager.load("proj-1") == ""

    def test_append_and_load(self, manager: ProjectContextManager) -> None:
        manager.append("proj-1", "requirement", "B2B 電商賣家", project_name="ad-fast")
        content = manager.load("proj-1")
        assert "B2B" in content
        assert "Requirements" in content

    def test_append_multiple_categories(self, manager: ProjectContextManager) -> None:
        manager.append("proj-1", "requirement", "圖片批量生成", project_name="ad-fast")
        manager.append("proj-1", "decision", "用 Sharp 不用 Canvas", project_name="ad-fast")
        content = manager.load("proj-1")
        assert "Sharp" in content
        assert "Requirements" in content
        assert "Decisions" in content

    def test_write_replaces_content(self, manager: ProjectContextManager) -> None:
        manager.append("proj-1", "requirement", "old", project_name="ad-fast")
        manager.write("proj-1", "# new content only")
        content = manager.load("proj-1")
        assert "new content only" in content
        assert "old" not in content

    def test_line_count(self, manager: ProjectContextManager) -> None:
        manager.write("proj-1", "\n".join([f"- line {i}" for i in range(80)]))
        assert manager.line_count("proj-1") == 80
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_project_context.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement ProjectContextManager**

```python
# shared/project_context.py
"""Project Context — per-project memory shared by all agents.

Stores requirements, decisions, constraints, and user preferences
discovered during the pipeline execution.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECTS_DIR = Path(__file__).resolve().parent.parent / "data" / "projects"

CATEGORY_HEADERS = {
    "requirement": "Requirements",
    "decision": "Decisions",
    "constraint": "Constraints",
    "user_preference": "User Preferences",
}


class ProjectContextManager:
    def __init__(self, projects_dir: Path | None = None) -> None:
        self._dir = projects_dir or PROJECTS_DIR

    def _context_path(self, project_id: str) -> Path:
        return self._dir / project_id / "context.md"

    def load(self, project_id: str) -> str:
        path = self._context_path(project_id)
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8").strip()

    def write(self, project_id: str, content: str) -> None:
        path = self._context_path(project_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        logger.info("Project context updated: %s", path)

    def append(
        self,
        project_id: str,
        category: str,
        content: str,
        project_name: str = "",
    ) -> None:
        path = self._context_path(project_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        today = date.today().isoformat()
        section_name = CATEGORY_HEADERS.get(category, category.title())
        tagged_entry = f"- [{today}] {content}"

        if not path.exists():
            header = f"# {project_name or project_id} — Project Context"
            file_content = f"{header}\n\n## {section_name}\n{tagged_entry}\n"
            path.write_text(file_content, encoding="utf-8")
            return

        file_content = path.read_text(encoding="utf-8")
        section_header = f"## {section_name}"
        if section_header in file_content:
            idx = file_content.index(section_header) + len(section_header)
            newline_idx = file_content.index("\n", idx)
            file_content = (
                file_content[:newline_idx + 1]
                + tagged_entry + "\n"
                + file_content[newline_idx + 1:]
            )
        else:
            file_content = file_content.rstrip() + f"\n\n## {section_name}\n{tagged_entry}\n"

        path.write_text(file_content, encoding="utf-8")

    def line_count(self, project_id: str) -> int:
        content = self.load(project_id)
        if not content:
            return 0
        return len(content.split("\n"))

    def dream_log_path(self, project_id: str) -> Path:
        return self._dir / project_id / "dream_log.md"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_project_context.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add shared/project_context.py tests/test_project_context.py
git commit -m "feat: add ProjectContextManager for per-project memory"
```

---

## Task 4: DreamConsolidator

**Files:**
- Create: `shared/dream.py`
- Test: `tests/test_dream.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_dream.py
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.dream import DreamConsolidator


@pytest.fixture
def tmp_souls_dir(tmp_path: Path) -> Path:
    d = tmp_path / "souls"
    d.mkdir()
    return d


@pytest.fixture
def tmp_projects_dir(tmp_path: Path) -> Path:
    d = tmp_path / "projects"
    d.mkdir()
    return d


@pytest.fixture
def consolidator(tmp_souls_dir: Path, tmp_projects_dir: Path) -> DreamConsolidator:
    from shared.soul_manager import SoulManager
    from shared.project_context import ProjectContextManager

    return DreamConsolidator(
        api_key="test-key",
        soul_manager=SoulManager(souls_dir=tmp_souls_dir),
        project_context_manager=ProjectContextManager(projects_dir=tmp_projects_dir),
        learnings_reader=lambda role=None: "no learnings",
    )


class TestDreamConsolidator:
    @pytest.mark.asyncio
    async def test_dream_soul_calls_api(self, consolidator: DreamConsolidator) -> None:
        # Seed a soul file
        consolidator._soul.write("frontend_engineer", "# Soul\n\n## 技術經驗\n- old entry")

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="# Soul\n\n## 技術經驗\n- consolidated entry")]

        with patch.object(
            consolidator, "_call_claude", new_callable=AsyncMock, return_value=mock_response
        ):
            await consolidator.dream_soul("frontend_engineer")

        content = consolidator._soul.load("frontend_engineer")
        assert "consolidated entry" in content

    @pytest.mark.asyncio
    async def test_dream_project_calls_api(self, consolidator: DreamConsolidator) -> None:
        consolidator._project_ctx.write("proj-1", "# Context\n\n## Requirements\n- old req")

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="# Context\n\n## Requirements\n- new req")]

        with patch.object(
            consolidator, "_call_claude", new_callable=AsyncMock, return_value=mock_response
        ):
            await consolidator.dream_project("proj-1")

        content = consolidator._project_ctx.load("proj-1")
        assert "new req" in content

    def test_dream_skips_empty_soul(self, consolidator: DreamConsolidator) -> None:
        import asyncio
        # Should not crash on empty soul
        loop = asyncio.new_event_loop()
        with patch.object(consolidator, "_call_claude", new_callable=AsyncMock) as mock:
            loop.run_until_complete(consolidator.dream_soul("nonexistent"))
        mock.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_dream.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement DreamConsolidator**

```python
# shared/dream.py
"""Auto-Dream — memory consolidation using direct Anthropic SDK calls.

Periodically cleans up agent souls and project contexts:
  - Deletes outdated info (fixed bugs, deleted files)
  - Merges duplicate entries
  - Converts relative dates to absolute dates
  - Resolves contradictions (keep latest)
  - Enforces line limits (100 for souls, 150 for projects)
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date, datetime, timezone

import anthropic

from shared.project_context import ProjectContextManager
from shared.soul_manager import SoulManager

logger = logging.getLogger(__name__)

SOUL_LINE_LIMIT = 100
PROJECT_LINE_LIMIT = 150
DREAM_MODEL = "claude-sonnet-4-6"

CONSOLIDATION_SYSTEM = (
    "你是記憶整理器。整理以下記憶檔案：\n"
    "1. 刪除過時資訊（已修復的 bug、已刪除的檔案）\n"
    "2. 合併重複條目\n"
    "3. 相對日期 → 絕對日期\n"
    "4. 矛盾經驗保留最新\n"
    "5. 控制在 {line_limit} 行以內\n"
    "6. 保持 markdown 格式，保留 section headers\n"
    "輸出整理後的完整檔案內容，不要其他說明。"
)


class DreamConsolidator:
    def __init__(
        self,
        api_key: str,
        soul_manager: SoulManager,
        project_context_manager: ProjectContextManager,
        learnings_reader: Callable[..., str] | None = None,
    ) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._soul = soul_manager
        self._project_ctx = project_context_manager
        self._read_learnings = learnings_reader or (lambda **_: "")

    async def close(self) -> None:
        await self._client.close()

    async def _call_claude(self, system: str, user_content: str) -> anthropic.types.Message:
        return await self._client.messages.create(
            model=DREAM_MODEL,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user_content}],
        )

    async def dream_soul(self, role: str) -> None:
        current = self._soul.load(role)
        if not current:
            logger.info("Dream skipped for %s: no existing soul", role)
            return

        learnings = self._read_learnings(role=role)
        system = CONSOLIDATION_SYSTEM.format(line_limit=SOUL_LINE_LIMIT)
        user_content = (
            f"現有記憶:\n{current}\n\n"
            f"近期學習紀錄:\n{learnings}\n\n"
            f"今天日期: {date.today().isoformat()}"
        )

        try:
            response = await self._call_claude(system, user_content)
            consolidated = response.content[0].text
            self._soul.write(role, consolidated)
            logger.info("Dream completed for soul: %s", role)
        except Exception as e:
            logger.error("Dream failed for soul %s: %s", role, e)

    async def dream_project(self, project_id: str) -> None:
        current = self._project_ctx.load(project_id)
        if not current:
            logger.info("Dream skipped for project %s: no existing context", project_id)
            return

        learnings = self._read_learnings()
        system = CONSOLIDATION_SYSTEM.format(line_limit=PROJECT_LINE_LIMIT)
        user_content = (
            f"現有專案記憶:\n{current}\n\n"
            f"近期學習紀錄:\n{learnings}\n\n"
            f"今天日期: {date.today().isoformat()}"
        )

        try:
            response = await self._call_claude(system, user_content)
            consolidated = response.content[0].text
            self._project_ctx.write(project_id, consolidated)
            logger.info("Dream completed for project: %s", project_id)
        except Exception as e:
            logger.error("Dream failed for project %s: %s", project_id, e)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_dream.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add shared/dream.py tests/test_dream.py
git commit -m "feat: add DreamConsolidator for memory consolidation"
```

---

## Task 5: Settings + Models updates

**Files:**
- Modify: `shared/config.py`
- Modify: `shared/models.py`

- [ ] **Step 1: Add new settings to config.py**

Add after line 33 (before `model_config`):

```python
    # Conversational agent settings
    listen_channels: str = "project-requests,agent-war-room"
    agent_ask_timeout_minutes: int = 30
    dream_soul_threshold: int = 10
    dream_project_threshold: int = 5
```

- [ ] **Step 2: Add AGENT_PERSONAS to models.py**

Add after `AGENT_IDENTITIES` dict (after line 166):

```python

# Agent personas for Discord webhook messages (username + avatar for conversational mode)
AGENT_PERSONAS: dict[AgentRole, dict[str, str]] = {
    role: {
        "username": identity["name"],
        "avatar_url": identity["avatar_url"],
    }
    for role, identity in AGENT_IDENTITIES.items()
}
```

- [ ] **Step 3: Verify existing tests still pass**

Run: `pytest tests/ -v`
Expected: All existing tests PASS

- [ ] **Step 4: Commit**

```bash
git add shared/config.py shared/models.py
git commit -m "feat: add conversational agent settings and AGENT_PERSONAS"
```

---

## Task 6: New tools + tool handlers in BaseAgent

**Files:**
- Modify: `shared/tools.py`
- Modify: `shared/agent_base.py`

- [ ] **Step 1: Add 4 new tool definitions to tools.py**

Add before `BUILD_TOOLS` definition (before line 385):

```python
TOOL_DISCORD_ASK_USER = {
    "name": "discord_ask_user",
    "description": "Ask the user a question in the Discord thread and wait for their reply. Use when you need clarification or a decision.",
    "input_schema": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The question to ask the user (in 繁體中文)",
            },
            "urgent": {
                "type": "boolean",
                "description": "If true, ping the user multiple times (default: false)",
            },
        },
        "required": ["question"],
    },
}

TOOL_DISCORD_DISCUSS = {
    "name": "discord_discuss",
    "description": "Post a message in the Discord thread to discuss with other agents or share observations. Does not wait for reply.",
    "input_schema": {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "The message to post (in 繁體中文)",
            },
        },
        "required": ["message"],
    },
}

TOOL_DISCORD_REPORT_BLOCKER = {
    "name": "discord_report_blocker",
    "description": "Report a blocking issue that requires user decision. Pings the user and waits for reply.",
    "input_schema": {
        "type": "object",
        "properties": {
            "description": {
                "type": "string",
                "description": "Description of the blocker and what decision is needed",
            },
        },
        "required": ["description"],
    },
}

TOOL_UPDATE_PROJECT_CONTEXT = {
    "name": "update_project_context",
    "description": "Record an important project decision, requirement, or constraint for other agents to reference.",
    "input_schema": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": ["requirement", "decision", "constraint", "user_preference"],
                "description": "Category of the information",
            },
            "content": {
                "type": "string",
                "description": "The information to record (in 繁體中文)",
            },
        },
        "required": ["category", "content"],
    },
}

# Conversational tools — available to all pipeline agents
CONVERSATIONAL_TOOLS = [
    TOOL_DISCORD_ASK_USER,
    TOOL_DISCORD_DISCUSS,
    TOOL_DISCORD_REPORT_BLOCKER,
    TOOL_UPDATE_PROJECT_CONTEXT,
]
```

Then update all tool sets to include conversational tools. Replace the `PLANNING_TOOLS`, `BUILD_TOOLS`, and `VERIFY_TOOLS` lists:

```python
PLANNING_TOOLS = [
    TOOL_LINEAR_UPDATE_ISSUE,
    TOOL_LINEAR_ADD_COMMENT,
    TOOL_LINEAR_CREATE_ISSUE,
    TOOL_LINEAR_QUERY_ISSUES,
    TOOL_DISCORD_NOTIFY,
    TOOL_COMPLETE_TASK,
] + CONVERSATIONAL_TOOLS

BUILD_TOOLS = [
    TOOL_LINEAR_UPDATE_ISSUE,
    TOOL_LINEAR_ADD_COMMENT,
    TOOL_LINEAR_CREATE_ISSUE,
    TOOL_DISCORD_NOTIFY,
    TOOL_GITHUB_LIST_REPOS,
    TOOL_GITHUB_CREATE_REPO,
    TOOL_GITHUB_CREATE_PR,
    TOOL_GITHUB_READ_FILE,
    TOOL_GITHUB_MERGE_PR,
    TOOL_VERCEL_DEPLOY,
    TOOL_VERCEL_CHECK_DEPLOY,
    TOOL_COMPLETE_TASK,
] + CONVERSATIONAL_TOOLS

VERIFY_TOOLS = [
    TOOL_LINEAR_UPDATE_ISSUE,
    TOOL_LINEAR_ADD_COMMENT,
    TOOL_LINEAR_CREATE_ISSUE,
    TOOL_LINEAR_QUERY_ISSUES,
    TOOL_DISCORD_NOTIFY,
    TOOL_GITHUB_READ_FILE,
    TOOL_GITHUB_MERGE_PR,
    TOOL_VERCEL_CHECK_DEPLOY,
    TOOL_COMPLETE_TASK,
] + CONVERSATIONAL_TOOLS
```

- [ ] **Step 2: Add tool handlers to agent_base.py**

Add these attributes to `BaseAgent.__init__` (after line 70):

```python
        self._conversation_store = None  # Set by dispatcher
        self._project_context = None  # Set by dispatcher
        self._thread_id: str | None = None  # Set by dispatcher
        self._project_id: str | None = None  # Set by dispatcher
```

Add new tool handlers in `_handle_tool_call` (before the `else` clause at line 340):

```python
            elif tool_name == "discord_ask_user":
                return await self._tool_discord_ask_user(tool_input), False

            elif tool_name == "discord_discuss":
                return await self._tool_discord_discuss(tool_input), False

            elif tool_name == "discord_report_blocker":
                return await self._tool_discord_report_blocker(tool_input), False

            elif tool_name == "update_project_context":
                return await self._tool_update_project_context(tool_input), False
```

Add the handler methods at the end of the class (after `_transition_status`):

```python
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
```

- [ ] **Step 3: Run all tests**

Run: `pytest tests/ -v`
Expected: All tests PASS (existing tool handling unchanged for known tools)

- [ ] **Step 4: Commit**

```bash
git add shared/tools.py shared/agent_base.py
git commit -m "feat: add conversational tools + handlers (ask_user, discuss, blocker, project_context)"
```

---

## Task 7: Extend agent_config.py — inject soul + project context

**Files:**
- Modify: `shared/agent_config.py`

- [ ] **Step 1: Update build_system_prompt to accept soul + project context**

Replace the `build_system_prompt` method (lines 77-97) with:

```python
    def build_system_prompt(
        self,
        role: str,
        base_prompt: str,
        *,
        soul_content: str = "",
        project_context: str = "",
        conversation_context: str = "",
    ) -> str:
        """Combine claude.md + skills + soul + project context + conversation + base_prompt."""
        parts: list[str] = []

        # 1. Global rules (claude.md)
        claude_md = self._dir / "claude.md"
        if claude_md.exists():
            parts.append(claude_md.read_text(encoding="utf-8").strip())

        # 2. Skills from agent config
        config = self.load_agent_config(role)
        if config and config.skills:
            for skill_name in config.skills:
                skill_content = self.read_skill(skill_name)
                if skill_content:
                    parts.append(f"## Skill: {skill_name}\n\n{skill_content}")

        # 3. Agent Soul (cross-project experience)
        if soul_content:
            parts.append(f"## 你的經驗記憶（跨專案）\n\n{soul_content}")

        # 4. Project Context (project-specific memory)
        if project_context:
            parts.append(f"## 專案脈絡\n\n{project_context}")

        # 5. Discord conversation context
        if conversation_context:
            parts.append(f"## Discord 對話脈絡\n\n{conversation_context}")

        # 6. Base prompt (hardcoded in agent class)
        parts.append(base_prompt)

        return "\n\n---\n\n".join(parts)
```

- [ ] **Step 2: Run existing agent_config tests**

Run: `pytest tests/test_agent_config.py -v`
Expected: All tests PASS (new params are keyword-only with defaults)

- [ ] **Step 3: Commit**

```bash
git add shared/agent_config.py
git commit -m "feat: extend build_system_prompt with soul, project context, conversation"
```

---

## Task 8: Extend DiscordNotifier — agent_speak

**Files:**
- Modify: `shared/discord_notifier.py`

- [ ] **Step 1: Add agent_speak method**

Add after `send_alert` method (after line 199):

```python
    async def agent_speak(
        self,
        thread_id: str,
        agent_role: AgentRole,
        content: str,
        conversation_store: Any | None = None,
    ) -> dict[str, Any] | None:
        """Send a plain text message via webhook with agent persona (for thread conversations)."""
        url = self._webhook_urls.get("agent_hub")
        if not url:
            return None

        identity = AGENT_IDENTITIES.get(agent_role, {})
        payload: dict[str, Any] = {
            "username": identity.get("name", str(agent_role)),
            "avatar_url": identity.get("avatar_url", ""),
            "content": content[:2000],  # Discord limit
        }

        try:
            request_url = f"{url}?wait=true&thread_id={thread_id}"
            resp = await self._client.post(request_url, json=payload)
            resp.raise_for_status()
            logger.info("Agent %s spoke in thread %s", agent_role, thread_id)

            # Record in conversation store if provided
            if conversation_store:
                from shared.conversation_store import Message
                from datetime import datetime, timezone
                conversation_store.append_message(thread_id, Message(
                    author_type="agent",
                    author_id=str(agent_role),
                    content=content,
                    timestamp=datetime.now(timezone.utc),
                ))

            return resp.json()
        except httpx.HTTPError as e:
            logger.error("Agent speak failed: %s", e)
            return None
```

- [ ] **Step 2: Verify existing tests**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add shared/discord_notifier.py
git commit -m "feat: add agent_speak method for thread conversations"
```

---

## Task 9: IntentRouter

**Files:**
- Create: `gateway/discord/intent_router.py`
- Test: `tests/test_intent_router.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_intent_router.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_intent_router.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement IntentRouter**

```python
# services/gateway/discord/intent_router.py
"""Intent classification using Claude Haiku for fast, cheap routing."""

from __future__ import annotations

import json
import logging
from typing import Literal

import anthropic
from pydantic import BaseModel

logger = logging.getLogger(__name__)

HAIKU_MODEL = "claude-haiku-4-5-20251001"

CLASSIFY_SYSTEM = """你是 Discord 訊息意圖分類器。根據訊息內容和頻道上下文，判斷用戶意圖。

回傳 JSON（不要 markdown code block）：
{
  "intent": "new_project" | "task_feedback" | "question" | "agent_command" | "conversation" | "irrelevant",
  "confidence": 0.0-1.0,
  "target_agent": null 或 agent role name（如 "frontend_engineer"）,
  "target_issue": null 或 issue identifier（如 "DRO-42"）,
  "summary": "一句話描述意圖"
}

意圖判斷規則：
- new_project: 「我想開發...」「建一個...」「新專案」「做一個...」
- task_feedback: 「改成...」「不對」「加功能」「需求變更」，通常提到特定 issue
- question: 「進度？」「測完了嗎？」「狀態如何」
- agent_command: 明確指定 agent 執行動作，如「叫 Frontend 重新部署」
- conversation: 在進行中的對話中回覆（通常在 thread 裡）
- irrelevant: 閒聊、與工作無關"""


class IntentResult(BaseModel):
    intent: Literal[
        "new_project", "task_feedback", "question",
        "agent_command", "conversation", "irrelevant"
    ]
    confidence: float = 0.0
    target_agent: str | None = None
    target_issue: str | None = None
    summary: str = ""


class IntentRouter:
    def __init__(self, api_key: str) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def close(self) -> None:
        await self._client.close()

    async def classify(self, message_content: str, channel_context: str) -> IntentResult:
        try:
            response = await self._client.messages.create(
                model=HAIKU_MODEL,
                max_tokens=256,
                system=CLASSIFY_SYSTEM,
                messages=[{
                    "role": "user",
                    "content": f"頻道: {channel_context}\n訊息: {message_content}",
                }],
            )
            text = response.content[0].text.strip()
            # Handle potential markdown code block wrapping
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            data = json.loads(text)
            return IntentResult(**data)
        except Exception as e:
            logger.error("Intent classification failed: %s", e)
            return IntentResult(intent="irrelevant", confidence=0.0, summary=f"Error: {e}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_intent_router.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add services/gateway/discord/intent_router.py tests/test_intent_router.py
git commit -m "feat: add IntentRouter with Haiku classification"
```

---

## Task 10: MultiTurnGatherer

**Files:**
- Create: `gateway/discord/gatherer.py`
- Test: `tests/test_gatherer.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_gatherer.py
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
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="ad-fast 主要面向什麼用戶？")]

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_gatherer.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement MultiTurnGatherer**

```python
# services/gateway/discord/gatherer.py
"""Multi-turn requirement gathering for new projects via DM or channel."""

from __future__ import annotations

import json
import logging
from typing import Any

import anthropic

from shared.conversation_store import ConversationStore, Message
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

HAIKU_MODEL = "claude-haiku-4-5-20251001"

GATHER_SYSTEM = """你是專案需求收集助手。用戶想建立一個新專案，你需要逐步收集以下資訊：

必填：
- 專案名稱
- 目標用戶
- 核心功能（至少 1-3 個）
- 技術 stack 偏好

選填：
- 平台限制（尺寸、格式等）
- 時程
- 第三方整合

規則：
- 每次只問一個問題
- 用繁體中文
- 簡潔友善
- 如果用戶已經在訊息中提供了資訊，不要重複問

根據目前對話，判斷還缺什麼資訊，然後問下一個問題。
如果資訊已經足夠，回覆 "READY" 開頭，後面接 JSON 摘要。"""

SUMMARY_SYSTEM = """根據對話內容，整理出專案需求摘要。回傳 JSON：
{
  "name": "專案名稱",
  "users": "目標用戶",
  "features": ["功能1", "功能2"],
  "stack": "技術 stack",
  "constraints": ["限制1"],
  "extras": "其他備註"
}"""


class MultiTurnGatherer:
    def __init__(
        self,
        api_key: str,
        conversation_store: ConversationStore,
    ) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._conversation_store = conversation_store

    async def close(self) -> None:
        await self._client.close()

    async def _ask_haiku(self, system: str, messages_text: str) -> str:
        response = await self._client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=512,
            system=system,
            messages=[{"role": "user", "content": messages_text}],
        )
        return response.content[0].text.strip()

    async def start_gathering(self, user_id: str, initial_message: str) -> str:
        dm = self._conversation_store.get_dm(user_id)
        if not dm:
            self._conversation_store.create_dm(user_id)

        self._conversation_store.update_dm_state(user_id, "gathering")
        self._conversation_store.append_dm_message(user_id, Message(
            author_type="user",
            author_id=user_id,
            content=initial_message,
            timestamp=datetime.now(timezone.utc),
        ))

        question = await self._ask_haiku(
            GATHER_SYSTEM,
            f"用戶說：{initial_message}\n\n請問第一個問題：",
        )
        return question

    async def continue_gathering(self, user_id: str, user_reply: str) -> dict[str, Any]:
        dm = self._conversation_store.get_dm(user_id)
        if not dm:
            return {"type": "error", "message": "No active gathering session"}

        self._conversation_store.append_dm_message(user_id, Message(
            author_type="user",
            author_id=user_id,
            content=user_reply,
            timestamp=datetime.now(timezone.utc),
        ))

        # Build conversation history
        history = "\n".join(
            f"{'用戶' if m.author_type == 'user' else 'Bot'}: {m.content}"
            for m in dm.messages
        )

        response_text = await self._ask_haiku(GATHER_SYSTEM, history)

        if response_text.startswith("READY"):
            self._conversation_store.update_dm_state(user_id, "confirming")
            return {"type": "confirm", "message": response_text}
        else:
            return {"type": "question", "message": response_text}

    async def build_summary(self, user_id: str) -> dict[str, Any]:
        dm = self._conversation_store.get_dm(user_id)
        if not dm:
            return {}

        history = "\n".join(
            f"{'用戶' if m.author_type == 'user' else 'Bot'}: {m.content}"
            for m in dm.messages
        )

        text = await self._ask_haiku(SUMMARY_SYSTEM, history)
        try:
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            return json.loads(text)
        except json.JSONDecodeError:
            return {"raw": text}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_gatherer.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add services/gateway/discord/gatherer.py tests/test_gatherer.py
git commit -m "feat: add MultiTurnGatherer for requirement collection"
```

---

## Task 11: ConversationListener

**Files:**
- Create: `gateway/discord/listener.py`
- Test: `tests/test_listener.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_listener.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_listener.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement ConversationListener**

```python
# services/gateway/discord/listener.py
"""Discord message listener — routes messages to intent router or conversation store."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import discord

from shared.conversation_store import ConversationStore, Message

logger = logging.getLogger(__name__)


class ConversationListener:
    def __init__(
        self,
        conversation_store: ConversationStore,
        intent_router: Any,
        gatherer: Any,
        dispatcher: Any,
        linear_client: Any,
        bot_user_id: int,
        listen_channels: list[str],
    ) -> None:
        self._conversation_store = conversation_store
        self._intent_router = intent_router
        self._gatherer = gatherer
        self._dispatcher = dispatcher
        self._linear = linear_client
        self._bot_user_id = bot_user_id
        self._listen_channels = listen_channels

    def should_ignore(self, message: discord.Message) -> bool:
        if message.author.id == self._bot_user_id:
            return True
        if message.author.bot and not self.is_webhook_message(message):
            return True
        return False

    def is_mention(self, message: discord.Message) -> bool:
        return any(m.id == self._bot_user_id for m in message.mentions)

    def is_monitored_channel(self, message: discord.Message) -> bool:
        channel_name = getattr(message.channel, "name", "")
        return channel_name in self._listen_channels

    def is_webhook_message(self, message: discord.Message) -> bool:
        return message.webhook_id is not None

    def is_in_tracked_thread(self, message: discord.Message) -> bool:
        thread_id = str(message.channel.id)
        return self._conversation_store.get_thread(thread_id) is not None

    def is_dm(self, message: discord.Message) -> bool:
        return isinstance(message.channel, discord.DMChannel)

    async def handle_message(self, message: discord.Message) -> None:
        if self.should_ignore(message):
            return

        # Webhook messages (from agents) → store only
        if self.is_webhook_message(message):
            if self.is_in_tracked_thread(message):
                self._store_message(message, author_type="agent")
            return

        # Check if this replies to a pending agent question
        thread_id = str(message.channel.id)
        if self.is_in_tracked_thread(message):
            self._store_message(message, author_type="user")
            if self._conversation_store.has_pending(thread_id):
                self._conversation_store.resolve_any_pending(thread_id, message.content)
                return

        # DM → multi-turn gatherer
        if self.is_dm(message):
            await self._handle_dm(message)
            return

        # Monitored channel or @mention → intent router
        if self.is_monitored_channel(message) or self.is_mention(message):
            await self._handle_intent(message)
            return

    async def _handle_dm(self, message: discord.Message) -> None:
        user_id = str(message.author.id)
        dm = self._conversation_store.get_dm(user_id)

        if dm and dm.state == "gathering":
            result = await self._gatherer.continue_gathering(user_id, message.content)
            if result["type"] == "confirm":
                summary = await self._gatherer.build_summary(user_id)
                # Format confirmation card
                confirm_msg = self._format_confirmation(summary)
                await message.channel.send(confirm_msg)
            else:
                await message.channel.send(result["message"])
        elif dm and dm.state == "confirming":
            if message.content.strip().lower() in ("ok", "yes", "好", "開始", "確認", "y"):
                self._conversation_store.update_dm_state(user_id, "confirmed")
                await message.channel.send("✅ 開始啟動 Pipeline...")
                await self._create_project_from_dm(message)
            else:
                self._conversation_store.update_dm_state(user_id, "gathering")
                result = await self._gatherer.continue_gathering(user_id, message.content)
                await message.channel.send(result["message"])
        else:
            # New conversation — check intent
            from services.gateway.discord.intent_router import IntentResult
            intent = await self._intent_router.classify(message.content, "DM")
            if intent.intent == "new_project":
                question = await self._gatherer.start_gathering(user_id, message.content)
                await message.channel.send(f"收到！讓我了解一下需求：\n\n{question}")
            elif intent.intent == "question":
                await self._handle_question(message, intent)
            else:
                await message.channel.send("你好！我可以幫你建立新專案或查詢進度。試試告訴我你想做什麼？")

    async def _handle_intent(self, message: discord.Message) -> None:
        channel_name = getattr(message.channel, "name", "unknown")
        intent = await self._intent_router.classify(message.content, channel_name)

        if intent.intent == "new_project":
            user_id = str(message.author.id)
            question = await self._gatherer.start_gathering(user_id, message.content)
            # Reply in thread to keep channel clean
            thread = await message.create_thread(name=f"需求收集: {message.content[:50]}")
            await thread.send(f"收到！讓我了解一下需求：\n\n{question}")

        elif intent.intent == "task_feedback" and intent.target_issue:
            await self._handle_feedback(message, intent)

        elif intent.intent == "question":
            await self._handle_question(message, intent)

        elif intent.intent == "agent_command" and intent.target_agent:
            await self._handle_agent_command(message, intent)

        elif intent.intent == "irrelevant":
            pass  # Silent in channels

    async def _handle_question(self, message: discord.Message, intent: Any) -> None:
        # Simple status query — reply directly
        await message.reply(f"正在查詢... ({intent.summary})")

    async def _handle_feedback(self, message: discord.Message, intent: Any) -> None:
        await message.reply(f"收到回饋，正在更新 {intent.target_issue}...")

    async def _handle_agent_command(self, message: discord.Message, intent: Any) -> None:
        await message.reply(f"正在派遣 {intent.target_agent}...")

    async def _create_project_from_dm(self, message: discord.Message) -> None:
        user_id = str(message.author.id)
        summary = await self._gatherer.build_summary(user_id)
        # Delegate to Linear project creation (reuse existing logic)
        # This will be wired up in the bot integration
        logger.info("Creating project from DM: %s", summary)

    def _store_message(self, message: discord.Message, author_type: str = "user") -> None:
        thread_id = str(message.channel.id)
        try:
            self._conversation_store.append_message(thread_id, Message(
                author_type=author_type,
                author_id=str(message.author.id) if author_type == "user" else str(message.author.name),
                content=message.content,
                timestamp=datetime.now(timezone.utc),
                reply_to=str(message.reference.message_id) if message.reference else None,
            ))
        except KeyError:
            pass  # Thread not tracked

    def _format_confirmation(self, summary: dict) -> str:
        name = summary.get("name", "Unknown")
        users = summary.get("users", "N/A")
        features = summary.get("features", [])
        stack = summary.get("stack", "N/A")
        constraints = summary.get("constraints", [])

        features_str = "\n".join(f"  - {f}" for f in features) if features else "  - N/A"
        constraints_str = "\n".join(f"  - {c}" for c in constraints) if constraints else "  - 無"

        return (
            f"**需求確認** ✅\n"
            f"```\n"
            f"專案：{name}\n"
            f"用戶：{users}\n"
            f"核心功能：\n{features_str}\n"
            f"Stack：{stack}\n"
            f"限制：\n{constraints_str}\n"
            f"```\n"
            f"確認要開始嗎？（回覆「開始」）"
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_listener.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add services/gateway/discord/listener.py tests/test_listener.py
git commit -m "feat: add ConversationListener for message routing"
```

---

## Task 12: Wire everything into bot.py and main.py

**Files:**
- Modify: `gateway/discord/bot.py`
- Modify: `gateway/main.py`

- [ ] **Step 1: Update bot.py — enable message_content intent + on_message**

Replace the `create_bot` function in `services/gateway/discord/bot.py`:

```python
def create_bot(
    *,
    linear_client: Any = None,
    claude_client: Any = None,
    discord_notifier: Any = None,
    dispatcher: Any = None,
    github_client: Any = None,
    metrics_store: Any = None,
    config_manager: Any = None,
    conversation_store: Any = None,
    intent_router: Any = None,
    gatherer: Any = None,
) -> commands.Bot:
    intents = discord.Intents.default()
    intents.guilds = True
    intents.messages = True
    intents.message_content = True  # Privileged intent — enable in Discord Developer Portal

    bot = commands.Bot(command_prefix="!", intents=intents)

    # Store client references on the bot instance for commands to use
    bot.linear_client = linear_client  # type: ignore[attr-defined]
    bot.claude_client = claude_client  # type: ignore[attr-defined]
    bot.discord_notifier = discord_notifier  # type: ignore[attr-defined]
    bot.dispatcher = dispatcher  # type: ignore[attr-defined]
    bot.github_client = github_client  # type: ignore[attr-defined]
    bot.metrics_store = metrics_store  # type: ignore[attr-defined]
    bot.config_manager = config_manager  # type: ignore[attr-defined]
    bot.conversation_store = conversation_store  # type: ignore[attr-defined]

    _listener = None  # Will be created after bot is ready

    @bot.event
    async def on_ready() -> None:
        nonlocal _listener
        logger.info("Discord bot connected as %s", bot.user)

        # Create listener now that we have bot.user.id
        if conversation_store and intent_router and gatherer:
            from shared.config import get_settings
            settings = get_settings()
            from .listener import ConversationListener
            _listener = ConversationListener(
                conversation_store=conversation_store,
                intent_router=intent_router,
                gatherer=gatherer,
                dispatcher=dispatcher,
                linear_client=linear_client,
                bot_user_id=bot.user.id,
                listen_channels=settings.listen_channels.split(","),
            )
            logger.info("ConversationListener initialized (channels: %s)", settings.listen_channels)

        # Sync slash commands
        try:
            synced = await bot.tree.sync()
            logger.info("Synced %d slash commands", len(synced))
        except Exception as e:
            logger.error("Failed to sync commands: %s", e)

    @bot.event
    async def on_message(message: discord.Message) -> None:
        if _listener:
            await _listener.handle_message(message)
        # Still process prefix commands (!)
        await bot.process_commands(message)

    setup_commands(bot)
    return bot
```

Update `start_bot` to pass new params:

```python
async def start_bot(
    token: str,
    *,
    linear_client: Any = None,
    claude_client: Any = None,
    discord_notifier: Any = None,
    dispatcher: Any = None,
    github_client: Any = None,
    metrics_store: Any = None,
    config_manager: Any = None,
    conversation_store: Any = None,
    intent_router: Any = None,
    gatherer: Any = None,
) -> None:
    global _bot, _bot_task
    _bot = create_bot(
        linear_client=linear_client,
        claude_client=claude_client,
        discord_notifier=discord_notifier,
        dispatcher=dispatcher,
        github_client=github_client,
        metrics_store=metrics_store,
        config_manager=config_manager,
        conversation_store=conversation_store,
        intent_router=intent_router,
        gatherer=gatherer,
    )
    _bot_task = asyncio.create_task(_bot.start(token))
    logger.info("Discord bot starting...")
```

- [ ] **Step 2: Update main.py — initialize new components**

Add imports after existing imports (after line 34):

```python
from shared.conversation_store import ConversationStore
from shared.soul_manager import SoulManager
from shared.project_context import ProjectContextManager
from shared.dream import DreamConsolidator
from .discord.intent_router import IntentRouter
from .discord.gatherer import MultiTurnGatherer
```

Add initialization in `lifespan` after `config_manager = AgentConfigManager()` (after line 66):

```python
    # Conversation + memory components
    conversation_store = ConversationStore()
    conversation_store.load()
    soul_manager = SoulManager()
    project_context_manager = ProjectContextManager()
    dream_consolidator = DreamConsolidator(
        api_key=settings.anthropic_api_key,
        soul_manager=soul_manager,
        project_context_manager=project_context_manager,
        learnings_reader=config_manager.read_learnings,
    )
    intent_router = IntentRouter(api_key=settings.anthropic_api_key)
    gatherer = MultiTurnGatherer(
        api_key=settings.anthropic_api_key,
        conversation_store=conversation_store,
    )
```

Store new components on `app.state` (after existing app.state assignments):

```python
    app.state.conversation_store = conversation_store
    app.state.soul_manager = soul_manager
    app.state.project_context_manager = project_context_manager
    app.state.dream_consolidator = dream_consolidator
```

Pass to `start_bot`:

```python
    if settings.discord_bot_token:
        await start_bot(
            settings.discord_bot_token,
            linear_client=linear_client,
            claude_client=claude_client,
            discord_notifier=discord_notifier,
            dispatcher=dispatcher,
            github_client=github_client,
            metrics_store=metrics_store,
            config_manager=config_manager,
            conversation_store=conversation_store,
            intent_router=intent_router,
            gatherer=gatherer,
        )
```

Add cleanup (before `logger.info("Gateway stopped")`):

```python
    await intent_router.close()
    await gatherer.close()
    await dream_consolidator.close()
```

- [ ] **Step 3: Run all tests**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add services/gateway/discord/bot.py services/gateway/main.py
git commit -m "feat: wire ConversationListener, IntentRouter, Gatherer into bot lifecycle"
```

---

## Task 13: Update dispatcher — dream triggers + agent context injection

**Files:**
- Modify: `shared/dispatcher.py`
- Modify: `shared/metrics.py`

- [ ] **Step 1: Add dream counter tracking to MetricsStore**

Add to `shared/metrics.py` after `_run_counter` in `__init__` (after line 45):

```python
        self._dream_counters: dict[str, int] = {}  # role/project_id → runs since last dream
```

Add these methods at the end of the `MetricsStore` class:

```python
    def increment_dream_counter(self, key: str) -> int:
        self._dream_counters[key] = self._dream_counters.get(key, 0) + 1
        return self._dream_counters[key]

    def reset_dream_counter(self, key: str) -> None:
        self._dream_counters[key] = 0

    def get_dream_counter(self, key: str) -> int:
        return self._dream_counters.get(key, 0)
```

- [ ] **Step 2: Add dream trigger + context injection to dispatcher.py**

Add to `AgentDispatcher.__init__` (after `self._vercel` on line 78):

```python
        self._conversation_store = None  # Set externally
        self._soul_manager = None  # Set externally
        self._project_context = None  # Set externally
        self._dream_consolidator = None  # Set externally
```

Add a setter method after `register_all`:

```python
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
```

In `_run_agent`, after the agent handler call succeeds (after `success = True` on line 155), add context injection before the handler call. Replace lines 140-145:

```python
        try:
            # Inject memory context into agent if available
            if hasattr(handler, '__self__') is False:
                # handler is a function — pass context via task payload
                task.payload["_conversation_store"] = self._conversation_store
                task.payload["_project_context"] = self._project_context
                task.payload["_soul_manager"] = self._soul_manager

            result = await handler(
                task, self._claude, self._linear, self._discord,
                github_client=self._github,
                vercel_client=self._vercel,
            ) or {}
```

Add `_maybe_dream` method at the end of the class (before `shutdown`):

```python
    async def _maybe_dream(self, agent_role: str, project_id: str = "") -> None:
        if not self._metrics_store or not self._dream_consolidator:
            return

        from shared.config import get_settings
        settings = get_settings()

        soul_count = self._metrics_store.increment_dream_counter(f"soul:{agent_role}")
        if soul_count >= settings.dream_soul_threshold:
            import asyncio
            asyncio.create_task(self._dream_consolidator.dream_soul(agent_role))
            self._metrics_store.reset_dream_counter(f"soul:{agent_role}")
            logger.info("Dream triggered for agent soul: %s", agent_role)

        if project_id:
            proj_count = self._metrics_store.increment_dream_counter(f"project:{project_id}")
            if proj_count >= settings.dream_project_threshold:
                import asyncio
                asyncio.create_task(self._dream_consolidator.dream_project(project_id))
                self._metrics_store.reset_dream_counter(f"project:{project_id}")
                logger.info("Dream triggered for project: %s", project_id)
```

Call `_maybe_dream` in the `finally` block of `_run_agent` (after metrics recording):

```python
            # Trigger dream consolidation if thresholds met
            project_id = task.payload.get("project_id", "")
            await self._maybe_dream(str(agent_role), project_id)
```

- [ ] **Step 3: Wire memory components in main.py**

Add after `register_all_agents(dispatcher)` in `main.py`:

```python
    dispatcher.set_memory_components(
        conversation_store=conversation_store,
        soul_manager=soul_manager,
        project_context=project_context_manager,
        dream_consolidator=dream_consolidator,
    )
```

- [ ] **Step 4: Run all tests**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add shared/dispatcher.py shared/metrics.py services/gateway/main.py
git commit -m "feat: add dream triggers + memory context injection in dispatcher"
```

---

## Task 14: Update BaseAgent.run — inject soul + context into system prompt

**Files:**
- Modify: `shared/agent_base.py`

- [ ] **Step 1: Update run() to use memory context**

In `BaseAgent.run`, after fetching issue context (after line 90), add:

```python
        # Extract memory components from payload (injected by dispatcher)
        self._conversation_store = payload.pop("_conversation_store", None)
        self._project_context = payload.pop("_project_context", None)
        soul_manager = payload.pop("_soul_manager", None)
        self._thread_id = payload.get("thread_id")
        self._project_id = payload.get("project_id")
```

Replace the system prompt building section (lines 92-95):

```python
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
```

After the agentic loop completes (after Discord notification, before `return result`), add soul reflection:

```python
        # Reflect and potentially update soul
        if soul_manager and result.get("summary"):
            from shared.soul_manager import SoulManager
            if isinstance(soul_manager, SoulManager):
                try:
                    await self._maybe_reflect(soul_manager, task, result)
                except Exception as e:
                    logger.warning("Soul reflection failed: %s", e)
```

Add the reflection method at the end of the class:

```python
    async def _maybe_reflect(
        self, soul_manager: Any, task: AgentTask, result: dict[str, Any]
    ) -> None:
        """Use Haiku to decide if this run produced experience worth remembering."""
        import anthropic

        # Only reflect on notable runs (failures, high tokens, or successful complex tasks)
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
            import json
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
```

- [ ] **Step 2: Run all tests**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add shared/agent_base.py
git commit -m "feat: inject soul/project/conversation context into agent system prompt + reflection"
```

---

## Task 15: Integration smoke test

**Files:**
- Create: `tests/test_integration_conversational.py`

- [ ] **Step 1: Write integration test**

```python
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
```

- [ ] **Step 2: Run integration test**

Run: `pytest tests/test_integration_conversational.py -v`
Expected: PASS

- [ ] **Step 3: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration_conversational.py
git commit -m "test: add integration smoke test for conversational agent flow"
```

---

## Summary of all tasks

| Task | Component | New/Modified | Tests |
|------|-----------|-------------|-------|
| 1 | ConversationStore | New | 8 tests |
| 2 | SoulManager | New | 5 tests |
| 3 | ProjectContextManager | New | 5 tests |
| 4 | DreamConsolidator | New | 3 tests |
| 5 | Settings + Models | Modified | verify existing |
| 6 | New tools + handlers | Modified | verify existing |
| 7 | agent_config.py prompt | Modified | verify existing |
| 8 | DiscordNotifier.agent_speak | Modified | verify existing |
| 9 | IntentRouter | New | 3 tests |
| 10 | MultiTurnGatherer | New | 3 tests |
| 11 | ConversationListener | New | 7 tests |
| 12 | Bot + Main wiring | Modified | verify existing |
| 13 | Dispatcher + Metrics dream | Modified | verify existing |
| 14 | BaseAgent context injection | Modified | verify existing |
| 15 | Integration smoke test | New | 1 test |

**Total: 15 tasks, ~35 new tests, 7 new files, 10 modified files**
