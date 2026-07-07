"""Recorded webhook delivery for idempotency + audit (spec: webhooks)."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class WebhookDelivery:
    id: UUID
    delivery_id: str  # X-GitHub-Delivery (idempotency key)
    event: str
    action: str | None
    repository_full_name: str | None
    outcome: str  # "processed" | "ignored" | "duplicate" | "error"
    received_at: datetime
