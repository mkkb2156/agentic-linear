FROM python:3.12-slim AS base

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY shared/ shared/
COPY services/ services/
COPY data/ data/

ENV LOG_LEVEL=info

# Default: run gateway. Override with --role for workers.
# Gateway: uvicorn services.gateway.main:app --host 0.0.0.0 --port 8000
# Worker:  python -m services.worker.main --role <role_name>
CMD uvicorn services.gateway.main:app --host 0.0.0.0 --port ${PORT:-8000} --log-level ${LOG_LEVEL}
