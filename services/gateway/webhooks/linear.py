from __future__ import annotations

import logging

from fastapi import APIRouter, Request, Response

from shared.linear_client import verify_webhook
from shared.models import LinearWebhookPayload
from services.gateway.router import EventRouter

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/linear")
async def linear_webhook(request: Request) -> Response:
    """
    Receive Linear webhook events.
    Must respond within 5 seconds (Linear retry: 1min → 1hr → 6hr).
    """
    body = await request.body()

    # Verify HMAC-SHA256 signature
    signature = request.headers.get("Linear-Signature", "")
    settings = request.app.state
    from shared.config import get_settings

    secret = get_settings().linear_webhook_secret
    if secret and not verify_webhook(body, signature, secret):
        logger.warning("Invalid webhook signature")
        return Response(status_code=401)

    # Parse payload
    import json

    try:
        raw = json.loads(body)
    except json.JSONDecodeError:
        return Response(status_code=400)

    payload = LinearWebhookPayload.model_validate(raw)
    delivery_id = request.headers.get("Linear-Delivery")

    logger.info(
        "Webhook received: action=%s type=%s delivery=%s",
        payload.action,
        payload.type,
        delivery_id,
    )

    # Route event to agent queue (in background to keep response fast)
    event_router = EventRouter(request.app.state.task_queue)
    # FastAPI BackgroundTasks could be used here, but since enqueue is fast,
    # we do it inline to keep it simple
    await event_router.route(payload, delivery_id=delivery_id)

    return Response(status_code=200)
