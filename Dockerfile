FROM python:3.12-slim AS base

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY shared/ shared/
COPY services/ services/

ENV LOG_LEVEL=info
CMD uvicorn services.gateway.main:app --host 0.0.0.0 --port ${PORT:-8000} --log-level ${LOG_LEVEL}
