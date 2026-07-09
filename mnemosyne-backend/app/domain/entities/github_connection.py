"""GitHub connection entity: an encrypted read credential (spec: github-connection).

Two credential kinds (design D1):
- ``pat``        — an encrypted fine-grained personal access token.
- ``github_app`` — a GitHub App installation: app id, installation id, and
  encrypted private key + webhook secret. Installation tokens are minted on
  demand and never stored.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.domain.value_objects.enums import ConnectionKind, ConnectionStatus

REQUIRED_PERMISSIONS = frozenset({"contents", "issues", "pull_requests", "metadata"})


@dataclass(slots=True)
class GitHubConnection:
    id: UUID
    owner: str  # user or organization login the credential resolves to
    owner_type: str  # "User" | "Organization"
    kind: ConnectionKind = ConnectionKind.PAT
    encrypted_token: bytes | None = None  # pat only
    token_hint: str = ""  # pat only: last 4 chars, the only fragment ever exposed
    # github_app only:
    app_id: str | None = None
    installation_id: str | None = None
    encrypted_private_key: bytes | None = None
    encrypted_webhook_secret: bytes | None = None
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

    def mark_pending_installation(self) -> None:
        self.status = ConnectionStatus.PENDING_INSTALLATION
