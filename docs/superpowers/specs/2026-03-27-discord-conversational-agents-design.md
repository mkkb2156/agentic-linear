# Discord Conversational Agents — Design Spec

**Date**: 2026-03-27
**Status**: Approved
**Scope**: Transform Discord bot from slash-command-driven to natural conversational multi-agent collaboration

---

## Problem

Current state: users must use `/slash` commands to trigger agent work. Agents communicate via Linear comments and Discord webhooks but cannot read Discord messages, respond to questions, or collaborate with each other conversationally.

Goal: agents behave like real team members — read conversations, reply, ask questions, discuss with each other, and autonomously execute tasks from natural language input.

## Architecture Overview

```
Discord Server
├─ #project-requests     ← Bot 監聽所有訊息
├─ #agent-war-room       ← Bot 監聽 + Agent threads
├─ DM with Bot           ← 多輪對話收集需求
└─ Any channel @mention  ← Bot 回應

                    ┌─────────────────────────────┐
                    │     ConversationListener     │
                    │  (唯一能讀訊息的：Discord Bot) │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │     Intent Router (Haiku)    │
                    │  分類意圖 → 決定動作          │
                    └──────────────┬──────────────┘
                                   │
          ┌────────────────────────┼─────────────────────────┐
          ▼                        ▼                         ▼
    new_project               task_feedback              question
    多輪對話收集需求           找 issue → 更新            查 context → 回答
    → Linear project          → 通知 agent
    → 啟動 pipeline

                    ┌─────────────────────────────┐
                    │     ConversationStore        │
                    │  (per-thread 對話池)          │
                    └──────────────┬──────────────┘
                                   │
          ┌────────────────────────┼────────────────────┐
          │                        │                    │
    Agent A 發言              Agent B 啟動          人類回覆
    (webhook 發送 +           (從 Store 讀取        (Bot 監聽 +
     寫入 Store)              完整 thread 脈絡)      寫入 Store)
```

### Key constraint

- **1 Discord Bot** — can read messages, respond to interactions
- **10+ Webhooks** — can only send messages (with unique agent persona name + avatar)
- Bot monitors ALL messages (including webhook-sent ones) to maintain complete ConversationStore

---

## Component Design

### 1. ConversationListener

**File**: `gateway/discord/listener.py`

Replaces pure slash-command interaction with full message monitoring.

**Discord intents required**: `message_content` (privileged intent — must enable in Discord Developer Portal)

**Listening rules**:

| Source | Condition | Action |
|--------|-----------|--------|
| `#project-requests` | Any user message | Intent Router |
| `#agent-war-room` | Any user message | Intent Router |
| Bot-created threads | Any message | Update ConversationStore + check pending questions |
| Any channel | @mention bot | Intent Router |
| DM | Any message | MultiTurnGatherer |
| Bot's own messages | Always | Ignore |
| Other bots/webhooks | In monitored threads | Store only (no Intent Router). Detected by matching `message.author.id` against known webhook IDs stored in config, or by checking `message.webhook_id is not None`. |

**Filter pipeline**:

```python
async def on_message(message):
    if message.author.bot and not is_agent_webhook(message):
        return
    if is_agent_webhook(message):
        conversation_store.append(thread_id, message)  # store only
        check_agent_discussions(message)                # agent-to-agent
        return
    # Human message
    if is_reply_to_pending_question(message):
        resume_waiting_agent(message)
        return
    if is_monitored_channel(message) or is_mention(message) or is_dm(message):
        await intent_router.route(message)
```

### 2. Intent Router

**File**: `gateway/discord/intent_router.py`

Uses Claude Haiku for fast, cheap intent classification.

**Intent categories**:

| Intent | Detection signal | Action |
|--------|-----------------|--------|
| `new_project` | 「我想開發...」「建一個...」「新專案」 | Start MultiTurnGatherer |
| `task_feedback` | 「改成...」「這個不對」「加一個功能」+ issue context | Find issue → update → notify agent |
| `question` | 「進度？」「測完了嗎？」「狀態？」 | Query Linear + metrics → reply |
| `agent_command` | 「@Frontend 重新部署」「叫 QA 再測一次」 | Dispatch specific agent |
| `conversation` | Reply in active thread / DM gathering state | Continue multi-turn context |
| `irrelevant` | Off-topic, casual chat | Silent (channel) / polite decline (DM) |

**Implementation**: Single Haiku call with structured output:

```python
async def classify(message_content, channel_context) -> IntentResult:
    response = await haiku_client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        system="Classify user intent. Return JSON.",
        messages=[{
            "role": "user",
            "content": f"Channel: {channel_context}\nMessage: {message_content}"
        }],
    )
    return IntentResult.model_validate_json(response.content[0].text)
```

**IntentResult schema**:

```python
class IntentResult(BaseModel):
    intent: Literal["new_project", "task_feedback", "question",
                     "agent_command", "conversation", "irrelevant"]
    confidence: float           # 0-1
    target_agent: str | None    # for agent_command
    target_issue: str | None    # for task_feedback
    summary: str                # one-line intent description
```

### 3. MultiTurnGatherer

**File**: `gateway/discord/gatherer.py`

Manages multi-turn requirement gathering conversations (DM or channel reply thread).

**States**:

```
idle → gathering → confirming → confirmed → pipeline_started
```

**Gathering flow**:

1. User expresses project idea → create `DMContext(state="gathering")`
2. Bot asks clarifying questions one at a time (Haiku generates questions based on what's missing)
3. Required fields: project name, target users, core features, tech stack
4. Optional fields: platform constraints, timeline, integrations
5. Once sufficient info → `state="confirming"` → present summary card
6. User confirms → `state="confirmed"` → create Linear project + issue → start pipeline

**Question generation**: Haiku with gathered context so far, asking what's still unclear.

**Timeout**: 30 minutes idle → `state="idle"`, notify user they can restart anytime.

### 4. ConversationStore

**File**: `shared/conversation_store.py`

In-memory conversation state with crash recovery via JSONL persistence.

**Data structures**:

```python
@dataclass
class Message:
    author_type: Literal["user", "agent", "bot"]
    author_id: str              # user_id or agent_role
    content: str
    timestamp: datetime
    reply_to: str | None        # reply reference
    metadata: dict              # tool results, attachments, etc.

@dataclass
class ThreadContext:
    thread_id: str
    issue_id: str               # Linear issue
    project_id: str             # Linear project
    messages: list[Message]
    participants: set[str]
    pending_questions: dict[str, PendingQuestion]  # agent_role → question
    created_at: datetime
    updated_at: datetime

@dataclass
class PendingQuestion:
    agent_role: str
    question: str
    asked_at: datetime
    timeout_minutes: int = 30
    callback: asyncio.Future    # resolved when user replies

@dataclass
class DMContext:
    user_id: str
    messages: list[Message]
    state: Literal["idle", "gathering", "confirming", "confirmed"]
    draft_project: dict         # accumulated requirements
```

**Persistence**:

```
data/conversations/{thread_id}.jsonl  — append on every write
Startup: rebuild in-memory state from JSONL files
Cleanup: archive threads with no activity for 7 days
```

**Context injection for agents**:

```python
async def build_agent_context(thread_id, agent_role) -> str:
    thread = store.get(thread_id)
    recent = thread.messages[-50:]

    # Summarize early messages if > 50
    if len(thread.messages) > 50:
        early_summary = await haiku_summarize(thread.messages[:-50])
        return f"[早期對話摘要]\n{early_summary}\n\n[近期對話]\n{format(recent)}"

    return format(recent)
```

### 5. Agent Personas

**File**: Extend `shared/models.py`

Each agent sends messages via webhook with unique identity:

```python
AGENT_PERSONAS = {
    AgentRole.PRODUCT_STRATEGIST: {
        "username": "🎯 Product Strategist",
        "avatar_url": "https://api.dicebear.com/...",  # existing
        "speak_style": "strategic",
    },
    # ... all 11 agents
}
```

**Speaking method** (extend `shared/discord_notifier.py`):

```python
async def agent_speak(thread_id, agent_role, content):
    persona = AGENT_PERSONAS[agent_role]
    await webhook.send(
        content=content,
        thread=discord.Object(id=thread_id),
        username=persona["username"],
        avatar_url=persona["avatar_url"],
    )
    conversation_store.append(thread_id, Message(
        author_type="agent",
        author_id=agent_role,
        content=content,
        timestamp=utcnow(),
    ))
```

### 6. Agent Await Mechanism

**File**: Modify `shared/agent_base.py`

New tools that pause the agentic loop and wait for human response:

**`discord_ask_user`** — Ask user a question, pause until reply:

```python
async def handle_discord_ask_user(thread_id, agent_role, question, timeout=30):
    future = asyncio.get_event_loop().create_future()
    conversation_store.set_pending(thread_id, agent_role, question, future)
    await agent_speak(thread_id, agent_role, question)  # includes @User

    try:
        reply = await asyncio.wait_for(future, timeout=timeout * 60)
        return {"status": "answered", "reply": reply}
    except asyncio.TimeoutError:
        conversation_store.clear_pending(thread_id, agent_role)
        return {"status": "timeout", "reply": None}
```

When Bot detects a user reply to a pending question → `future.set_result(reply_content)` → agent resumes.

**`discord_discuss`** — Post a message to thread (no wait):

```python
# Fire and forget — for agent-to-agent commentary
async def handle_discord_discuss(thread_id, agent_role, message):
    await agent_speak(thread_id, agent_role, message)
    return {"status": "sent"}
```

**`discord_report_blocker`** — Report a blocking issue with urgency:

```python
async def handle_discord_report_blocker(thread_id, agent_role, description):
    msg = f"⚠️ **Blocker**\n{description}\n\n@User 需要你的決定"
    await agent_speak(thread_id, agent_role, msg)
    # Same await mechanism as discord_ask_user
```

**Timeout behavior**: When `discord_ask_user` times out, the tool returns `{"status": "timeout"}`. The agent's system prompt instructs it to make a best-guess decision and note it in the thread:

```
「等待超時，我先用 [assumption] 繼續。如果不對請隨時修正。」
```

### 7. Thread Lifecycle

**Creation**: When pipeline starts for an issue:

```python
async def create_issue_thread(issue_id, issue_title, channel):
    thread = await channel.create_thread(
        name=f"[{issue_id}] {issue_title}",
        type=discord.ChannelType.public_thread,
    )
    conversation_store.create_thread(thread.id, issue_id, project_id)
    return thread
```

**During pipeline**: All agents post in the thread. Humans can join anytime.

**Completion**: Bot posts summary embed → thread remains accessible (not archived immediately).

**Cleanup**: Threads with no activity for 7 days → Bot posts final summary → archive.

---

## Memory Architecture

### Two-Layer Memory

```
Agent Soul (跨專案)                    Project Context (專案特定)
agent_config/souls/                    data/projects/{project_id}/
├─ frontend_engineer.md                ├─ context.md
├─ backend_engineer.md                 ├─ conversations.jsonl
├─ qa_engineer.md                      └─ dream_log.md
└─ ...
```

### 8. SoulManager

**File**: `shared/soul_manager.py`

Per-agent persistent memory that accumulates cross-project experience.

**Soul file format** (`agent_config/souls/{role}.md`):

```markdown
# {emoji} {Agent Name} — Soul

## 技術經驗
- [2026-03-20] Supabase Storage 上傳 > 5MB 要用 resumable upload
- [2026-03-25] Next.js Route Handler 不能用 edge runtime 搭 Sharp

## 協作模式
- System Architect 給的 schema 通常需要補 index，主動提出
- QA 常漏測 edge case：空陣列、超長字串，先自己處理

## 踩過的坑
- [2026-03-20] ad-fast: Sharp 處理大量圖片記憶體要設 limit

## 偏好
- 先寫 migration 再寫 API，避免 schema drift
```

**Write timing**: After each agent run completes, a Haiku reflection call determines if anything is worth saving:

```python
async def maybe_update_soul(role, task, result):
    prompt = f"""
    任務摘要: {result['summary']}
    Token: {result['tokens_used']}
    成功: {result['success']}
    錯誤: {result.get('error_message', '')}

    判斷是否有值得長期記住的經驗。
    回答 JSON: {{"worth_saving": bool, "category": str, "entry": str}}
    """
    reflection = await haiku_call(prompt)
    if reflection.worth_saving:
        soul_manager.append(role, reflection.category, reflection.entry)
```

**Size limit**: 100 lines per soul file. Enforced by Auto-Dream.

### 9. ProjectContextManager

**File**: `shared/project_context.py`

Per-project memory shared by all agents working on that project.

**Context file format** (`data/projects/{project_id}/context.md`):

```markdown
# ad-fast — Project Context

## Requirements
- B2B 電商賣家，蝦皮 + Meta 投放
- 第一版：圖片批量生成 + 多平台適配 + AI 文案

## Decisions
- [2026-03-27] Stack: Next.js + Supabase（標準 stack）
- [2026-03-27] 圖片處理用 Sharp，不用 Canvas（效能考量）
- [2026-03-27] Storage: Supabase Pro（需 > 50MB 支援）

## Constraints
- 蝦皮素材 800x800, Meta 動態消息 1200x628
- 第一版不做影片

## User Preferences
- 用戶偏好批次操作 UI，不要逐一上傳
```

**Agent tool for writing**:

```python
TOOL_UPDATE_PROJECT_CONTEXT = {
    "name": "update_project_context",
    "description": "記錄專案重要決策或發現，供後續 agent 參考",
    "input_schema": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": ["requirement", "decision", "constraint", "user_preference"]
            },
            "content": {"type": "string"}
        },
        "required": ["category", "content"]
    }
}
```

**Size limit**: 150 lines per context file. Enforced by Auto-Dream.

### 10. Auto-Dream (DreamConsolidator)

**File**: `shared/dream.py`

Memory consolidation using direct Anthropic SDK calls (no agentic loop).

**Trigger conditions** (any one):

| Condition | Target |
|-----------|--------|
| Agent has 10+ runs since last dream | That agent's soul |
| Project has 5+ agent runs since last dream | That project's context |
| Manual: `/admin dream [agent\|project]` | Specified target |

**Trigger integration** (in `dispatcher.py`):

```python
async def _maybe_dream(agent_role, project_id):
    soul_runs = metrics_store.count_since_last_dream(agent_role)
    project_runs = metrics_store.count_project_since_last_dream(project_id)

    if soul_runs >= 10:
        asyncio.create_task(dream_consolidator.dream_soul(agent_role))

    if project_runs >= 5:
        asyncio.create_task(dream_consolidator.dream_project(project_id))
```

**Dream phases**:

```
Phase 1 — Read
  Read soul.md or context.md + recent learning_log entries

Phase 2 — Consolidate (single Anthropic SDK call)
  - Delete outdated info (fixed bugs, deleted files)
  - Merge duplicate entries
  - Convert relative dates → absolute dates
  - Resolve contradictions (keep latest)
  - Compress to stay within line limit

Phase 3 — Write back
  Overwrite soul.md or context.md
  Append to dream_log.md (what changed and why)
```

**Implementation**:

```python
async def dream_soul(agent_role):
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    current_soul = soul_manager.load(agent_role)
    recent_learnings = load_recent_learnings(agent_role)

    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=(
            "你是記憶整理器。整理以下 agent 記憶檔案：\n"
            "1. 刪除過時資訊（已修復的 bug、已刪除的檔案）\n"
            "2. 合併重複條目\n"
            "3. 相對日期 → 絕對日期\n"
            "4. 矛盾經驗保留最新\n"
            "5. 控制在 100 行以內\n"
            "6. 保持 markdown 格式\n"
            "輸出整理後的完整檔案內容，不要其他說明。"
        ),
        messages=[{
            "role": "user",
            "content": (
                f"現有記憶:\n{current_soul}\n\n"
                f"近期學習紀錄:\n{recent_learnings}\n\n"
                f"今天日期: {date.today().isoformat()}"
            )
        }],
    )

    consolidated = response.content[0].text
    soul_manager.write(agent_role, consolidated)
    dream_log.append(agent_role, "soul", current_soul, consolidated)
    metrics_store.reset_dream_counter(agent_role)
```

**dream_project** follows the same pattern with 150-line limit.

---

## System Prompt Enhancement

Modify existing `build_system_prompt` in `shared/agent_config.py`:

```python
def build_system_prompt(role, base_prompt, project_id=None, thread_id=None):
    parts = []

    # 1. Existing: global rules
    parts.append(load_claude_md())

    # 2. Existing: skills
    parts.append(load_skills(role))

    # 3. NEW: Agent Soul
    soul = soul_manager.load(role)
    if soul:
        parts.append(f"## 你的經驗記憶（跨專案）\n{soul}")

    # 4. NEW: Project Context
    if project_id:
        ctx = project_context_manager.load(project_id)
        if ctx:
            parts.append(f"## 專案脈絡\n{ctx}")

    # 5. NEW: Thread conversation context
    if thread_id:
        conv = conversation_store.build_agent_context(thread_id, role)
        if conv:
            parts.append(f"## Discord 對話脈絡\n{conv}")

    # 6. Existing: agent base prompt
    parts.append(base_prompt)

    return "\n---\n".join(parts)
```

---

## New Tools Summary

Added to `shared/tools.py`:

| Tool | Available to | Purpose |
|------|-------------|---------|
| `discord_ask_user` | All agents | Ask user a question, pause until reply (30min timeout) |
| `discord_discuss` | All agents | Post message in thread (no wait) |
| `discord_report_blocker` | All agents | Report blocker with @User ping |
| `update_project_context` | All agents | Write to project context.md |

---

## Modified Files Summary

| File | Changes |
|------|---------|
| `gateway/discord/bot.py` | Add `on_message` handler, enable `message_content` intent |
| `gateway/discord/commands.py` | Keep slash commands (backward compatible) |
| `gateway/main.py` | Initialize new managers in lifespan |
| `shared/agent_base.py` | Add await mechanism for `discord_ask_user` tool |
| `shared/tools.py` | Add 4 new tools |
| `shared/models.py` | Extend AGENT_IDENTITIES → AGENT_PERSONAS |
| `shared/dispatcher.py` | Add `_maybe_dream`, thread creation, pass thread_id |
| `shared/agent_config.py` | Inject soul + project context into system prompt |
| `shared/discord_notifier.py` | Add `agent_speak` with thread + persona support |

## New Files Summary

| File | Purpose |
|------|---------|
| `gateway/discord/listener.py` | ConversationListener — message monitoring |
| `gateway/discord/intent_router.py` | Intent classification (Haiku) |
| `gateway/discord/gatherer.py` | Multi-turn requirement gathering |
| `shared/conversation_store.py` | In-memory + JSONL conversation state |
| `shared/soul_manager.py` | Agent soul read/write |
| `shared/project_context.py` | Project context read/write |
| `shared/dream.py` | Auto-Dream consolidation |

---

## Environment Variables

New required:

| Variable | Purpose |
|----------|---------|
| (none new) | Reuses existing `ANTHROPIC_API_KEY` for Haiku calls |

New optional:

| Variable | Default | Purpose |
|----------|---------|---------|
| `LISTEN_CHANNELS` | `project-requests,agent-war-room` | Channels to monitor |
| `AGENT_ASK_TIMEOUT_MINUTES` | `30` | Default timeout for agent questions |
| `DREAM_SOUL_THRESHOLD` | `10` | Runs before soul dream triggers |
| `DREAM_PROJECT_THRESHOLD` | `5` | Runs before project dream triggers |

---

## Discord Developer Portal Changes

Must enable **Message Content Intent** (privileged) in the bot settings for `on_message` to receive message content.

---

## End-to-End Flow

See Section 5 in brainstorming session for complete timeline walkthrough:
User says "我想開發 ad-fast" → multi-turn gathering → Linear project → agent pipeline with thread collaboration → auto-dream consolidation.
