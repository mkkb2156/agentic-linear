# GDS Agent Platform

Drone168 Multi-Agent Pipeline — AI-powered development automation platform.

## Overview

10 AI Agents automate the full software development lifecycle, driven by Linear issue status changes, powered by Claude, and monitored through Discord.

### 10 Agents

| Agent | Role | Trigger |
|-------|------|---------|
| 🎯 Product Strategist | PRD & strategy analysis | Manual |
| 📐 Spec Architect | Technical spec design | Strategy Complete |
| 🏗️ System Architect | System architecture (Opus) | Spec Complete |
| ⚛️ Frontend Engineer | UI components | Architecture Complete |
| 🔧 Backend Engineer | API & database | Architecture Complete |
| 🧪 QA Engineer | Test plans & validation | Implementation Done |
| 🚀 DevOps | CI/CD & deployment | QA Passed |
| 📋 Release Manager | Changelog & releases | Deployed |
| 🖥️ Infra Ops | Infrastructure monitoring | Alert Triggered |
| ☁️ Cloud Ops | Cloud config checks | Deploy Complete |

### Architecture

```
Linear status change → Webhook → Gateway → Router (DAG) → Dispatcher → Agent
  → Agent runs Claude Tool Use loop → Posts results to Linear → Transitions status
  → Next webhook fires → Next agent triggered
```

- **Task management**: Linear (source of truth)
- **Code**: GitHub
- **Product DB**: Supabase
- **AI**: Claude Sonnet 4.6 (90%) + Opus 4.6 (10%)
- **Monitoring**: Discord (1 Bot + 10 Webhook identities)
- **Deploy**: Railway (single service)

## Quick Start

```bash
cp .env.example .env     # Fill in API keys
docker-compose up        # Start gateway
pytest tests/            # Run tests (23 passing)
```

## Project Structure

```
services/
  gateway/         → Webhook receiver + agent dispatcher (FastAPI)
  planning/agents/ → Product Strategist, Spec Architect, System Architect
  build/agents/    → Frontend Engineer, Backend Engineer
  verify/agents/   → QA Engineer, DevOps, Release Manager
  ops/agents/      → Infra Ops, Cloud Ops
shared/            → Agent base, dispatcher, tools, clients, models
tests/             → 23 tests (webhook, routing, agent base, dispatcher)
```
