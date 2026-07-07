"""Public GitHub webhook receiver (spec: webhooks; design D3).

Unauthenticated by CyberdyneAuth — gated by HMAC-SHA256 signature validation
against the installation's webhook secret. Verifies the raw body BEFORE
parsing, dedupes by delivery id, and dispatches to incremental sync.
"""

import json
import logging
from typing import Any

from fastapi import APIRouter, Request, Response

from app.domain.entities.webhook_event import WebhookEvent
from app.domain.services.webhook_signature import verify_signature

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


@router.post("/github", include_in_schema=True)
async def github_webhook(request: Request) -> Response:
    container = request.app.state.container
    body = await request.body()

    try:
        payload = json.loads(body) if body else {}
    except json.JSONDecodeError:
        return Response(status_code=400, content="invalid JSON")

    installation_id = _dig(payload, "installation", "id")
    secret = None
    if installation_id is not None:
        secret = await container.connection_use_cases.webhook_secret_for_installation(
            str(installation_id)
        )
    signature = request.headers.get("X-Hub-Signature-256")
    if secret is None or not verify_signature(secret, body, signature):
        return Response(status_code=401, content="invalid signature")

    event = WebhookEvent(
        delivery_id=request.headers.get("X-GitHub-Delivery", ""),
        event=request.headers.get("X-GitHub-Event", ""),
        action=payload.get("action"),
        installation_id=str(installation_id) if installation_id is not None else None,
        repository_full_name=_dig(payload, "repository", "full_name"),
        payload=payload,
    )
    try:
        outcome = await container.process_webhook.process(event)
    except Exception:
        logger.exception("webhook processing failed for delivery %s", event.delivery_id)
        return Response(status_code=202, content="accepted")
    return Response(status_code=200, content=outcome)


def _dig(payload: dict[str, Any], *keys: str) -> Any:
    node: object = payload
    for key in keys:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node
