"""Audit service: records sensitive and denied operations (spec: auth)."""

from datetime import UTC, datetime
from uuid import uuid4

from app.domain.entities.audit_record import AuditRecord
from app.domain.ports.persistence_ports import AuditPort
from app.domain.value_objects.identity import CallerIdentity


class AuditService:
    def __init__(self, audit_port: AuditPort) -> None:
        self._audit = audit_port

    async def record(
        self,
        caller: CallerIdentity | None,
        operation: str,
        *,
        target: str | None = None,
        outcome: str = "ok",
    ) -> None:
        await self._audit.record(
            AuditRecord(
                id=uuid4(),
                subject=caller.subject if caller else "anonymous",
                client_id=caller.client_id if caller else None,
                operation=operation,
                target=target,
                outcome=outcome,
                occurred_at=datetime.now(UTC),
            )
        )

    async def record_denied(
        self, caller: CallerIdentity | None, operation: str, *, target: str | None = None
    ) -> None:
        await self.record(caller, operation, target=target, outcome="denied")
