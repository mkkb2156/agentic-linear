# Drone168 Multi-Agent Pipeline - Phase 1 Implementation Plan

## Context

The Drone168 Dev Pipeline project needs a Multi-Agent Platform that deploys 10 AI Agent roles as automated services on Railway. The system is driven by Linear Webhook status changes, uses PostgreSQL SKIP LOCKED as a task queue (via Supabase), Discord for monitoring, and Claude API for AI processing. The repository is completely empty — this plan covers Phase 1 (基礎建設), establishing the entire foundation.

**Source:** [Linear Architecture Doc (808a387bbf1b)](https://linear.app/drone168/document/系統架構multi-agent-pipeline-自動化平台-808a387bbf1b)

---

## Step 1: Project Scaffolding

Create the mono-repo structure, Python packaging, and config files.

### Files to create:

- **`pyproject.toml`** — Root Python project using `uv` or `pip`. Dependencies:
  - `fastapi`, `uvicorn[standard]`, `asyncpg`, `httpx`
  - `discord.py>=2.0`, `anthropic`
  - `pydantic`, `pydantic-settings`
  - `python-dotenv`
  - Dev: `pytest`, `pytest-asyncio`, `ruff`

- **`.gitignore`** — Python, venv, .env, __pycache__, .mypy_cache, etc.

- **`.env.example`** — Placeholder env vars:
  ```
  # Supabase
  DATABASE_URL=postgresql://...
  # Linear
  LINEAR_API_KEY=lin_api_...
  LINEAR_WEBHOOK_SECRET=...
  # Claude
  ANTHROPIC_API_KEY=sk-ant-...
  # Discord
  DISCORD_BOT_TOKEN=...
  DISCORD_WEBHOOK_URL_AGENT_HUB=...
  ```

- **`CLAUDE.md`** — Project conventions for AI agents

### Directory structure:
```
services/
  gateway/
  planning/
  build/
  verify/
  ops/
shared/
migrations/
tests/
```

Each service gets an `__init__.py`. `shared/` gets `__init__.py`.

---

## Step 2: Shared Modules (shared/)

These are the foundation used by all services.

### `shared/config.py`
- Pydantic Settings class loading from env vars
- Fields: `database_url`, `linear_api_key`, `linear_webhook_secret`, `anthropic_api_key`, `discord_bot_token`, `discord_webhook_urls` (dict per agent)
- Singleton pattern via `@lru_cache`

### `shared/models.py`
- Pydantic models for:
  - `AgentTask` — mirrors the `agent_tasks` DB table
  - `LinearWebhookPayload` — `action`, `type`, `data`, `updatedFrom`, delivery header
  - `AgentRole` enum — all 10 agent roles
  - `QueueName` enum — `planning`, `build`, `verify`, `ops`
  - `TaskStatus` enum — `pending`, `processing`, `completed`, `failed`, `dead`
  - `StatusTransition` — mapping of Linear status → target queue + agent role

### `shared/queue.py`
- `TaskQueue` class using `asyncpg` connection pool
- `enqueue(queue_name, agent_role, issue_id, payload, idempotency_key)` — INSERT with ON CONFLICT DO NOTHING
- `fetch_next(queue_name)` — UPDATE ... FOR UPDATE SKIP LOCKED pattern
- `complete(task_id, tokens_used, model_used)`
- `fail(task_id, error_message)` — increment retry_count, set status to `failed` or `dead` if max retries
- `setup_listen(queue_name)` — LISTEN on channel for instant notification
- `notify(queue_name)` — NOTIFY after enqueue

### `shared/linear_client.py`
- `LinearClient` class using `httpx.AsyncClient`
- GraphQL endpoint: `https://api.linear.app/graphql`
- Methods: `get_issue(id)`, `update_issue(id, data)`, `add_comment(issue_id, body)`, `create_issue(data)`, `query_issues(filter)`
- HMAC-SHA256 webhook signature verification: `verify_webhook(body, signature, secret)`
- Rate limit awareness via response headers

### `shared/claude_client.py`
- `ClaudeClient` class wrapping `anthropic.AsyncAnthropic`
- `execute(agent_role, system_prompt, messages, tools)` — routes to Sonnet by default, Opus for specific roles (System Architect) or on escalation flag
- Token tracking: returns `(response, tokens_used, model_used)`
- Retry with exponential backoff for 429/529

### `shared/discord_notifier.py`
- `DiscordNotifier` class
- Agent identity map: 10 agents → name, emoji, color hex
- `notify(agent_role, channel, embed_data)` — sends via webhook with agent's username + avatar
- `create_thread(channel_id, title)` — via Bot API
- Embed builder helper: consistent format with agent color + emoji

---

## Step 3: Database Migration

### `migrations/001_create_agent_tasks.sql`
```sql
CREATE TABLE agent_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    queue_name VARCHAR(50) NOT NULL,
    agent_role VARCHAR(50) NOT NULL,
    issue_id VARCHAR(20) NOT NULL,
    project_id UUID,
    payload JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(20) DEFAULT 'pending',
    retry_count INT DEFAULT 0,
    max_retries INT DEFAULT 3,
    model_used VARCHAR(30),
    tokens_used INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_message TEXT,
    idempotency_key VARCHAR(100) UNIQUE
);

CREATE INDEX idx_tasks_pending ON agent_tasks (queue_name, created_at)
    WHERE status = 'pending';
CREATE INDEX idx_tasks_issue ON agent_tasks (issue_id);
```

---

## Step 4: Webhook Gateway Service (services/gateway/)

### `services/gateway/main.py`
- FastAPI app with lifespan (startup: init DB pool, start Discord bot; shutdown: cleanup)
- `GET /health` — health check endpoint
- Mount webhook and Discord routers
- CORS middleware if needed

### `services/gateway/webhooks/__init__.py` + `linear.py`
- `POST /webhooks/linear` endpoint
- Verify HMAC-SHA256 signature using `shared.linear_client.verify_webhook`
- Extract `Linear-Delivery` header for idempotency
- Parse payload into `LinearWebhookPayload` model
- Respond HTTP 200 immediately (within 5 sec requirement)
- Background task: route event via `router.py`

### `services/gateway/webhooks/github.py`
- Stub `POST /webhooks/github` — placeholder for Phase 3

### `services/gateway/router.py`
- `EventRouter` class
- Status transition routing table (dict mapping status → queue_name + agent_role)
- `route(event)` — detect status change from `updatedFrom`, look up target, enqueue task
- Handle `Architecture Complete` → enqueue BOTH frontend + backend (parallel)
- Validation: only forward transitions allowed (DAG enforcement)

### `services/gateway/discord/bot.py`
- `discord.py` Bot setup with basic `on_ready` event
- Intents: guilds, messages
- Stub slash command registration

### `services/gateway/discord/commands.py`
- Stub slash commands: `/agent status`, `/pipeline view`
- Placeholder implementations that return "Coming in Phase 2"

### `services/gateway/discord/embeds.py`
- `build_status_change_embed(issue, old_status, new_status, agent_role)`
- `build_task_complete_embed(task, result_summary)`
- Uses agent identity map for colors/emojis

---

## Step 5: Worker Service Stubs

Each worker follows the same pattern. Phase 1 implements the worker loop; actual agent logic comes in Phase 2+.

### `services/planning/main.py` (template for all workers)
- Async main loop:
  1. Init DB pool
  2. LISTEN on queue channel
  3. Loop: `fetch_next(queue_name)` → if task, process it → complete/fail
  4. On notification, wake up and fetch
- `process_task(task)` — dispatches to agent by `agent_role`
- Graceful shutdown on SIGTERM

### `services/planning/agents/__init__.py`
- Agent registry: maps role string → agent handler function

### `services/planning/agents/product_strategist.py` (stub)
- `async def execute(task, claude_client, linear_client, discord_notifier)`
- Phase 1: logs task received, returns placeholder result
- Sets up the contract that Phase 2 will implement

### Same stub pattern for all other agents across build/, verify/, ops/

---

## Step 6: Docker & Deployment Config

### `Dockerfile` (root, multi-stage)
- Base: `python:3.12-slim`
- Install dependencies from pyproject.toml
- `ARG SERVICE_NAME` to select which service to run
- CMD: `uvicorn services.{SERVICE_NAME}.main:app` (gateway) or `python -m services.{SERVICE_NAME}.main` (workers)

### `docker-compose.yml`
- Services: `gateway`, `planning-worker`, `build-worker`, `verify-worker`, `ops-worker`
- `postgres` service for local dev (PostgreSQL 15)
- Shared `.env` file
- All services depend on postgres
- Gateway exposes port 8000

### `railway.toml`
- Health check config, restart policy
- Comment noting per-service Root Directory config in Railway UI

---

## Step 7: Tests

### `tests/test_webhook_signature.py`
- Test HMAC-SHA256 verification (valid + invalid signatures)

### `tests/test_router.py`
- Test status transition routing table
- Test DAG enforcement (no backward transitions)
- Test parallel dispatch for `Architecture Complete`

### `tests/test_queue.py`
- Test enqueue + fetch_next with SKIP LOCKED
- Test idempotency (duplicate key rejected)
- Test fail + retry logic

---

## File Summary (all files to create)

```
.gitignore
.env.example
pyproject.toml
CLAUDE.md
Dockerfile
docker-compose.yml
railway.toml
migrations/001_create_agent_tasks.sql
shared/__init__.py
shared/config.py
shared/models.py
shared/queue.py
shared/linear_client.py
shared/claude_client.py
shared/discord_notifier.py
services/__init__.py
services/gateway/__init__.py
services/gateway/main.py
services/gateway/router.py
services/gateway/webhooks/__init__.py
services/gateway/webhooks/linear.py
services/gateway/webhooks/github.py
services/gateway/discord/__init__.py
services/gateway/discord/bot.py
services/gateway/discord/commands.py
services/gateway/discord/embeds.py
services/planning/__init__.py
services/planning/main.py
services/planning/agents/__init__.py
services/planning/agents/product_strategist.py
services/planning/agents/spec_architect.py
services/planning/agents/system_architect.py
services/build/__init__.py
services/build/main.py
services/build/agents/__init__.py
services/build/agents/frontend_engineer.py
services/build/agents/backend_engineer.py
services/verify/__init__.py
services/verify/main.py
services/verify/agents/__init__.py
services/verify/agents/qa_engineer.py
services/verify/agents/devops.py
services/verify/agents/release_manager.py
services/ops/__init__.py
services/ops/main.py
services/ops/agents/__init__.py
services/ops/agents/infra_ops.py
services/ops/agents/cloud_ops.py
tests/__init__.py
tests/test_webhook_signature.py
tests/test_router.py
tests/test_queue.py
```

---

## Verification

1. **Docker Compose Up:** `docker-compose up` starts all services + local Postgres
2. **Health Check:** `curl http://localhost:8000/health` returns 200
3. **DB Migration:** Run migration SQL against local Postgres, verify `agent_tasks` table
4. **Webhook Test:** `curl -X POST http://localhost:8000/webhooks/linear` with test payload + valid HMAC → task enqueued
5. **Queue Test:** Verify planning-worker picks up the enqueued task and processes it
6. **Tests Pass:** `pytest tests/` all green
7. **Discord Bot:** Bot connects and logs "Ready" (with valid token)
