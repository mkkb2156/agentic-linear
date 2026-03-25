# Drone168 Multi-Agent Pipeline — Implementation Status

## Context

GDS (一般無人機服務) 標準化軟體開發流程，採用 AI Agent 驅動的 10 階段 Pipeline。
Linear 為 source of truth（tasks/issues），GitHub 管理程式碼，Supabase 為產品後端資料庫。

**Source:** [Linear Architecture Doc](https://linear.app/drone168/document/系統架構multi-agent-pipeline-自動化平台-808a387bbf1b)

---

## Architecture

```
Linear status change
  → Webhook POST /webhooks/linear
  → Gateway (FastAPI)
  → EventRouter (DAG validation — forward transitions only)
  → AgentDispatcher.dispatch() → asyncio background task
  → Agent runs Claude Tool Use loop (max 15 turns)
  → Agent posts results to Linear (comments, sub-issues)
  → Agent transitions issue status via Linear API
  → Linear fires next webhook → next agent triggered
```

### Single Service
One Railway service (`gateway`) handles everything:
- Receives Linear/GitHub webhooks
- Validates pipeline DAG transitions
- Dispatches all 10 agents as background asyncio tasks
- Reports to Discord via webhook embeds

### Key Design Decisions
- **No intermediate database queue** — Linear is the task queue
- **Supabase** is for the product's backend database, not agentic workflow
- **Idempotency** via in-memory TTL cache (Linear-Delivery header)
- **Model routing**: Claude Sonnet 4.6 (90%) + Opus 4.6 (10%, System Architect only)

---

## 10 Agents

| # | Agent | Role | Trigger Status | Output |
|---|-------|------|---------------|--------|
| 1 | 🎯 Product Strategist | PRD 撰寫 | (manual start) | Strategy Complete |
| 2 | 📐 Spec Architect | 技術規格 | Strategy Complete | Spec Complete |
| 3 | 🏗️ System Architect | 系統架構 (Opus) | Spec Complete | Architecture Complete |
| 4 | ⚛️ Frontend Engineer | 前端開發 | Architecture Complete | Implementation Done |
| 5 | 🔧 Backend Engineer | 後端開發 | Architecture Complete | Implementation Done |
| 6 | 🧪 QA Engineer | 測試品質 | Implementation Done | QA Passed |
| 7 | 🚀 DevOps | CI/CD 部署 | QA Passed | Deployed |
| 8 | 📋 Release Manager | 版本發行 | Deployed | Deploy Complete |
| 9 | 🖥️ Infra Ops | 基礎設施 | Alert Triggered | — |
| 10 | ☁️ Cloud Ops | 雲端營運 | Deploy Complete | — |

Agents 4+5 run in parallel after Architecture Complete.
Agents 9+10 are continuous (triggered by events, not the main pipeline).

---

## Pipeline DAG

```
Strategy Complete → Spec Complete → Architecture Complete
                                      ├→ Frontend Engineer ─┐
                                      └→ Backend Engineer  ─┤
                                                            ↓
                                    Implementation Done → QA Passed → Deployed → Deploy Complete
                                                                                     ↓
                                                                                  Cloud Ops
Alert Triggered → Infra Ops
```

---

## Implementation Status

### ✅ Phase 1 — Foundation (Complete)
- FastAPI webhook gateway with HMAC-SHA256 verification
- Event router with DAG-enforced pipeline transitions
- Claude API client (Sonnet/Opus routing + retry)
- Discord notifier (10 agent identities, embeds, threads)
- Docker / docker-compose / Railway config

### ✅ Phase 2-4 — Agent Framework + All 10 Agents (Complete)
- `BaseAgent` class with Claude Tool Use agentic loop
- 6 tool definitions (Linear CRUD, Discord notify, complete_task)
- All 10 agents with role-specific system prompts
- Real Linear API: state lookup by name, status transitions, comment history
- Enhanced Discord: started/completed notifications, token stats, milestones

### ✅ Architecture Refactor — Remove PostgreSQL Queue (Complete)
- Removed: asyncpg, SKIP LOCKED queue, 4 worker services, migrations
- Added: `AgentDispatcher` (asyncio background tasks + in-memory idempotency)
- Consolidated from 5 services → 1 service (gateway)
- 23 tests passing

### 🔲 Phase 5 — Deployment & Integration (Next)
- [ ] Add custom Linear workflow states (Strategy Complete, Spec Complete, etc.)
- [ ] Deploy gateway to Railway
- [ ] Set up Discord webhooks (agent_hub, dashboard, alerts, deploy_log)
- [ ] Configure environment variables on Railway
- [ ] End-to-end integration test with real Linear issue
- [ ] Set up GitHub webhook for PR events

### 🔲 Phase 6 — Production Hardening
- [ ] Structured logging (JSON) for Railway log aggregation
- [ ] Token budget tracking per issue (daily/weekly reports)
- [ ] Rate limit handling for Linear API (pagination, throttling)
- [ ] Graceful shutdown (wait for active agents before exit)
- [ ] Health check with active agent count
- [ ] Error recovery: agent retry with exponential backoff

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.12+, async/await |
| Framework | FastAPI + uvicorn |
| AI | Claude Sonnet 4.6 / Opus 4.6 (Anthropic API) |
| Task Management | Linear (issues, status transitions, comments) |
| Code | GitHub (PRs, branches, CI) |
| Product DB | Supabase (PostgreSQL, Auth, Storage) |
| Deploy | Railway (single service) |
| Monitoring | Discord (1 Bot + webhook embeds) |
| Validation | Pydantic |
| HTTP | httpx |
| Testing | pytest + pytest-asyncio |
| Linting | Ruff (line-length 100) |

---

## Project Structure

```
services/
  gateway/
    main.py              → FastAPI app + lifespan
    agents.py            → Central registry (10 agents)
    router.py            → DAG-enforced event routing
    webhooks/linear.py   → Linear webhook endpoint
    webhooks/github.py   → GitHub webhook endpoint (stub)
    discord/bot.py       → Discord bot
    discord/commands.py  → Slash commands (stub)
    discord/embeds.py    → Embed builders
  planning/agents/       → Product Strategist, Spec Architect, System Architect
  build/agents/          → Frontend Engineer, Backend Engineer
  verify/agents/         → QA Engineer, DevOps, Release Manager
  ops/agents/            → Infra Ops, Cloud Ops
shared/
  agent_base.py          → BaseAgent + AgentTask + Claude Tool Use loop
  dispatcher.py          → AgentDispatcher (asyncio tasks + idempotency)
  tools.py               → Tool definitions for Claude Tool Use
  claude_client.py       → Anthropic API client
  linear_client.py       → Linear GraphQL client
  discord_notifier.py    → Discord webhook notifier
  models.py              → AgentRole, pipeline DAG, webhook models
  config.py              → Settings (env vars)
tests/
  test_webhook_signature.py
  test_router.py
  test_agent_base.py
  test_dispatcher.py
```

---

## Running Locally

```bash
cp .env.example .env     # Fill in API keys
docker-compose up        # Start gateway service
pytest tests/            # Run tests (23 passing)
```

---

## Deployment Guide (Phase 5)

### Step 1: Create Linear Custom Workflow States

```bash
LINEAR_API_KEY=lin_api_xxx python scripts/setup_linear.py
```

This creates 8 pipeline states in the Drone168 team:
`Strategy Complete`, `Spec Complete`, `Architecture Complete`,
`Implementation Done`, `QA Passed`, `Deployed`, `Deploy Complete`, `Alert Triggered`

### Step 2: Deploy to Railway

1. Create a Railway project, link to this GitHub repo
2. Add environment variables:
   - `LINEAR_API_KEY`, `LINEAR_WEBHOOK_SECRET`
   - `ANTHROPIC_API_KEY`
   - `DISCORD_BOT_TOKEN`
   - `DISCORD_WEBHOOK_URL_AGENT_HUB`, `DISCORD_WEBHOOK_URL_DASHBOARD`
   - `DISCORD_WEBHOOK_URL_ALERTS`, `DISCORD_WEBHOOK_URL_DEPLOY_LOG`
3. Deploy — Railway will build from `Dockerfile` and expose the service
4. Verify: `curl https://your-app.railway.app/health`

### Step 3: Set up Discord Webhooks

1. Create 4 webhooks in Discord server settings:
   - `#agent-hub` → `DISCORD_WEBHOOK_URL_AGENT_HUB`
   - `#dashboard` → `DISCORD_WEBHOOK_URL_DASHBOARD`
   - `#alerts` → `DISCORD_WEBHOOK_URL_ALERTS`
   - `#deploy-log` → `DISCORD_WEBHOOK_URL_DEPLOY_LOG`
2. Add URLs to Railway environment variables

### Step 4: Create Linear Webhook

```bash
LINEAR_API_KEY=lin_api_xxx \
GATEWAY_URL=https://your-app.railway.app \
LINEAR_WEBHOOK_SECRET=your-secret \
python scripts/setup_linear.py
```

Or manually: Linear Settings → API → Webhooks → Create:
- URL: `https://your-app.railway.app/webhooks/linear`
- Secret: same as `LINEAR_WEBHOOK_SECRET` env var
- Events: Issue status changes

### Step 5: E2E Integration Test

```bash
# Test against deployed gateway
python scripts/test_e2e.py https://your-app.railway.app

# Test against local
python scripts/test_e2e.py http://localhost:8000
```

Tests: health check, webhook delivery, idempotency, signature validation, DAG enforcement.

---

## Linear Project

**Project:** Drone168 Dev Pipeline (In Progress)
**Milestones:** M1-M10 (one per pipeline stage)
**Platform Issues:** DRO-15 (Done), DRO-16 (Done), DRO-17 (Done)
**Next:** DRO-18 (Phase 5: Deploy + Integration Test)
**Pipeline Issues:** DRO-5~14 (Todo, with blocking relations)
