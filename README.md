# GDS Agent Platform

Drone168 Multi-Agent Pipeline — AI-powered development automation platform.

## Overview

Deploys 10 AI Agent roles as automated services on Railway, driven by Linear Webhook status changes, with Discord monitoring.

### 10 Agents

| Agent | Role | Service |
|-------|------|---------|
| Product Strategist | PRD & strategy analysis | planning-worker |
| Spec Architect | API contract & spec design | planning-worker |
| System Architect | Cross-component architecture | planning-worker |
| Frontend Engineer | UI component development | build-worker |
| Backend Engineer | API & database development | build-worker |
| QA Engineer | Test case generation & validation | verify-worker |
| DevOps | CI/CD & deployment | verify-worker |
| Release Manager | Changelog & release coordination | verify-worker |
| Infra Ops | Infrastructure monitoring | ops-worker |
| Cloud Ops | Cloud configuration checks | ops-worker |

### Architecture

- **Task Queue**: PostgreSQL `SKIP LOCKED` (via Supabase)
- **AI Models**: Claude Sonnet (90%) + Opus (10%)
- **Comms**: Discord (1 Bot + 10 Webhook identities)
- **Trigger**: Linear Issue status changes → agent handoffs (DAG-enforced)

## Quick Start

```bash
# Local development
cp .env.example .env
docker-compose up

# Run tests
pip install -e ".[dev]"
pytest tests/
```

## Project Structure

```
services/
  gateway/     → webhook-gateway (FastAPI + Discord Bot)
  planning/    → planning-worker (Strategist, Spec, System Architect)
  build/       → build-worker (Frontend, Backend Engineer)
  verify/      → verify-worker (QA, DevOps, Release Manager)
  ops/         → ops-worker (Infra Ops, Cloud Ops) — cron
shared/        → shared modules (queue, clients, models, config)
migrations/    → PostgreSQL schema migrations
tests/         → test suite
```
