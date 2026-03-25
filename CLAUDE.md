# GDS Agent Platform

## Project Overview
Multi-Agent Pipeline platform for Drone168. 10 AI agents automated via Linear Webhooks, deployed on Railway, monitored through Discord.

## Architecture
- **1 Railway service**: gateway (webhook receiver + agent dispatcher)
- **Task management**: Linear (issues + status transitions = task queue)
- **Code management**: GitHub (PRs, branches)
- **Product database**: Supabase (PostgreSQL, Auth, Storage) — NOT for agentic workflow
- **AI**: Claude Sonnet 4.6 (90%) + Opus 4.6 (10%)
- **Comms**: Discord (1 Bot + 10 Webhooks)

## Code Conventions
- Python 3.12+, async/await throughout
- Pydantic for all data models
- httpx for HTTP clients
- Type hints on all public functions
- Ruff for linting (line length 100)

## Running Locally
```bash
docker-compose up        # Start gateway service
pytest tests/            # Run tests
```

## Key Patterns
- Linear status changes drive agent handoffs (DAG-enforced)
- Agents dispatched as asyncio background tasks (no intermediate queue)
- Idempotency via in-memory TTL cache (Linear-Delivery header)
- All agents share tools: linear_client, claude_client, discord_notifier
- BaseAgent runs Claude Tool Use agentic loop (max 15 turns)
