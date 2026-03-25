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
    Dispatches agents as background tasks — responds immediately.
    """
    body = await request.body()

    # Verify HMAC-SHA256 signature
    signature = request.headers.get("Linear-Signature", "")
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

    # Route event → dispatch agents as background tasks
    event_router = EventRouter(request.app.state.dispatcher)
    await event_router.route(payload, delivery_id=delivery_id)

    return Response(status_code=200)
