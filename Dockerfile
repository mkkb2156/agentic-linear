FROM python:3.12-slim AS base

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY shared/ shared/
COPY services/ services/

ARG SERVICE_NAME=gateway

ENV SERVICE_NAME=${SERVICE_NAME}

# Gateway runs FastAPI via uvicorn; workers run as Python modules
CMD if [ "$SERVICE_NAME" = "gateway" ]; then \
        uvicorn services.gateway.main:app --host 0.0.0.0 --port ${PORT:-8000}; \
    else \
        python -m services.${SERVICE_NAME}.main; \
    fi
