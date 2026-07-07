"""Captured OpenSpec change from a repository."""

from dataclasses import dataclass, field
from uuid import UUID

from app.domain.value_objects.enums import OpenSpecStatus


@dataclass(slots=True)
class OpenSpecChange:
    id: UUID
    repository_id: UUID
    change_id: str
    path: str
    status: OpenSpecStatus
    proposal: str | None = None
    design: str | None = None
    tasks: str | None = None
    affected_specs: list[str] = field(default_factory=list)
    content_hash: str = ""
