"""Audit record for sensitive and denied operations (spec: auth)."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AuditRecord:
    id: UUID
    subject: str  # caller sub, or "anonymous" for unauthenticated denials
    client_id: str | None
    operation: str
    target: str | None  # e.g. repository full name or connection id
    outcome: str  # "ok" | "denied"
    occurred_at: datetime
