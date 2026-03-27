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
