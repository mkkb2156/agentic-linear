# GDS Agent Platform

## Project Overview
Multi-Agent Pipeline platform for Drone168. 10 AI agents automated via Linear Webhooks, deployed on Railway, monitored through Discord.

## Architecture
- **5 Railway services**: webhook-gateway, planning-worker, build-worker, verify-worker, ops-worker
- **Task queue**: PostgreSQL `SKIP LOCKED` via Supabase
- **AI**: Claude Sonnet (90%) + Opus (10%)
- **Comms**: Discord (1 Bot + 10 Webhooks)

## Code Conventions
- Python 3.12+, async/await throughout
- Pydantic for all data models
- asyncpg for database access (no ORM)
- httpx for HTTP clients
- Type hints on all public functions
- Ruff for linting (line length 100)

## Running Locally
```bash
docker-compose up        # Start all services + Postgres
pytest tests/            # Run tests
```

## Key Patterns
- Workers use LISTEN/NOTIFY + FOR UPDATE SKIP LOCKED for task pulling
- Linear status changes drive agent handoffs (DAG-enforced)
- All agents share tools: linear_client, claude_client, discord_notifier
- Idempotency via Linear-Delivery header stored in idempotency_key
