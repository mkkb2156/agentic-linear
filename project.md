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

## 11 Agents

| # | Agent | Role | Trigger Status | Output |
|---|-------|------|---------------|--------|
| 1 | 🎯 策略師 | PRD 撰寫 | (manual / Discord) | Strategy Complete |
| 2 | 📐 規格師 | 技術規格 | Strategy Complete | Spec Complete |
| 3 | 🏗️ 架構師 | 系統架構 (Opus) | Spec Complete | Architecture Complete |
| 4 | ⚛️ 前端工程師 | 前端開發 | Architecture Complete | Implementation Done |
| 5 | 🔧 後端工程師 | 後端開發 | Architecture Complete | Implementation Done |
| 6 | 🧪 測試工程師 | 測試品質 | Implementation Done | QA Passed |
| 7 | 🚀 部署官 | CI/CD 部署 | QA Passed | Deployed |
| 8 | 📋 發版管理 | 版本發行 | Deployed | Deploy Complete |
| 9 | 🖥️ 維運官 | 基礎設施 | Alert Triggered | — |
| 10 | ☁️ 雲端官 | 雲端營運 | Deploy Complete | — |
| 11 | 🛡️ 管理官 | Admin (metrics, skills, learning) | /admin 或自動觸發 | — |

Agents 4+5 run in parallel after Architecture Complete.
Agents 9+10 are continuous (triggered by events, not the main pipeline).
Agent 11 (Admin) is outside the DAG — triggered manually or every 10 agent runs.

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
- `BaseAgent` class with Claude Tool Use agentic loop (max 15 turns)
- 6 tool definitions (Linear CRUD, Discord notify, complete_task)
- All 10 agents with role-specific system prompts
- Real Linear API: state lookup by name, status transitions, comment history
- Enhanced Discord: started/completed notifications, token stats, milestones

### ✅ Architecture Refactor — Remove PostgreSQL Queue (Complete)
- Removed: asyncpg, SKIP LOCKED queue, 4 worker services, migrations
- Added: `AgentDispatcher` (asyncio background tasks + in-memory idempotency)
- Consolidated from 5 services → 1 service (gateway)

### ✅ Phase 5 — Deployment & Integration (Complete)
- 8 custom Linear workflow states created (setup_linear.py)
- Railway deployed: `agentic-linear.up.railway.app`
- Linear webhook → Railway gateway
- Discord 4 webhooks + per-agent avatar personas (DiceBear)
- E2E test 5/5 passing
- Pipeline 端到端驗證: DRO-19 (Todo App) + DRO-20 (Skills System) — 全 pipeline 自動完成

### ✅ Phase 6 — Production Bug Fixes (Complete)
- Fix: router handles real Linear webhook format (flat stateId in updatedFrom)
- Fix: auto-resolve issue UUID in all tool calls (Claude sends DRO-20, API needs UUID)
- Fix: resolve teamId from issue context for sub-issue creation
- Fix: configure Python root logger (all app logs were silently dropped)
- Fix: increase max_tokens 4096→16384 + nudge Claude to use tools when it responds with text
- 25 tests passing

### ✅ Phase 7 — Discord Commands + GitHub Integration (Complete)
- Discord slash commands: `/project`, `/run`, `/status`, `/agent`
- GitHub API client: create_branch, push_file, get_file, create_pull_request
- Dynamic repo management: list_repos, create_repo, find_or_create_repo
- Agent tools: github_create_pr, github_read_file, github_list_repos, github_create_repo
- Config: github_token, github_repo_owner, vercel_token, supabase_access_token

### 🔨 Phase 8 — Admin Agent + Self-Learning (In Progress)
- [ ] Metrics persistence (AgentRunRecord + MetricsStore → data/metrics.json)
- [ ] Agent Config system (claude.md + skills/*.md + agents/*.yaml)
- [ ] Skills loading in BaseAgent (auto-enhanced system prompts)
- [ ] Admin Agent (#11) — query metrics, manage configs, generate reports
- [ ] Self-learning loop (capture → trigger every 10 runs → Admin analyzes + optimizes)
- [ ] /admin Discord command (report / config / learn)

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
  github_client.py       → GitHub REST API client
  discord_notifier.py    → Discord webhook notifier
  models.py              → AgentRole, pipeline DAG, webhook models
  config.py              → Settings (env vars)
  metrics.py             → MetricsStore (Phase 8)
  agent_config.py        → AgentConfigManager (Phase 8)
  agent_config/
    claude.md            → 全域最高規範
    skills/              → 領域知識 .md 文件
    agents/              → Per-agent YAML 配置
    learnings/           → 學習紀錄
scripts/
  setup_linear.py        → 建立 workflow states + webhook
  test_e2e.py            → E2E 整合測試
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

## Linear Projects

### Drone168 Dev Pipeline
**Status:** In Progress
**Milestones:** M1-M10 (one per pipeline stage)
**Platform Issues:** DRO-15 (Done), DRO-16 (Done), DRO-17 (Done), DRO-18 (Done)
**Pipeline Issues:** DRO-5~14 (M1~M10, Todo)
**Test Issues:** DRO-19 (Todo App, Done), DRO-20 (Skills System, Pipeline Complete)

### Agent Skills & Config System
**Status:** In Progress
**Milestones:** M1~M6
**Issue:** DRO-20 (Pipeline complete — 8 agents produced full design docs)
**Next:** Implement Admin Agent + Skills engine (Phase 8)

### Gateway
**URL:** `agentic-linear.up.railway.app`
**Health:** `/health` → agents_registered: 10, agents_active: N
**Discord:** `/project`, `/run`, `/status`, `/agent`
