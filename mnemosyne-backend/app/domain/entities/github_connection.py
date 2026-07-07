"""GitHub connection entity: an encrypted read credential (spec: github-connection)."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.domain.value_objects.enums import ConnectionStatus

REQUIRED_PERMISSIONS = frozenset({"contents", "issues", "pull_requests", "metadata"})


@dataclass(slots=True)
class GitHubConnection:
    id: UUID
    owner: str  # user or organization login the credential resolves to
    owner_type: str  # "User" | "Organization"
    encrypted_token: bytes
    token_hint: str  # last 4 chars, the only fragment ever exposed
    permissions: list[str] = field(default_factory=list)
    status: ConnectionStatus = ConnectionStatus.ACTIVE
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @staticmethod
    def missing_permissions(granted: set[str]) -> set[str]:
        return set(REQUIRED_PERMISSIONS) - granted

    def mark_broken(self) -> None:
        self.status = ConnectionStatus.BROKEN

    def mark_active(self) -> None:
        self.status = ConnectionStatus.ACTIVE
