"""GitHub credential lifecycle use cases (spec: github-connection)."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from app.application.errors import (
    InvalidCredentialError,
    MissingPermissionsError,
    UnknownResourceError,
)
from app.domain.entities.github_connection import GitHubConnection
from app.domain.ports.github_port import GitHubAuthError, GitHubPort
from app.domain.ports.persistence_ports import ConnectionPort


class TokenCipher(Protocol):
    def encrypt(self, plaintext: str) -> bytes: ...

    def decrypt(self, ciphertext: bytes) -> str: ...


@dataclass(frozen=True, slots=True)
class ConnectionView:
    """What the API is allowed to expose — never the credential (spec: github-connection)."""

    id: UUID
    owner: str
    owner_type: str
    token_hint: str
    permissions: list[str]
    status: str


def _view(connection: GitHubConnection) -> ConnectionView:
    return ConnectionView(
        id=connection.id,
        owner=connection.owner,
        owner_type=connection.owner_type,
        token_hint=connection.token_hint,
        permissions=list(connection.permissions),
        status=connection.status.value,
    )


class GitHubConnectionUseCases:
    def __init__(
        self, connections: ConnectionPort, github: GitHubPort, cipher: TokenCipher
    ) -> None:
        self._connections = connections
        self._github = github
        self._cipher = cipher

    async def connect(self, token: str) -> ConnectionView:
        """Validate a PAT with GitHub, then persist it encrypted."""
        try:
            info = await self._github.validate_token(token)
        except GitHubAuthError as exc:
            raise InvalidCredentialError(str(exc)) from exc
        missing = GitHubConnection.missing_permissions(info.permissions)
        if missing:
            raise MissingPermissionsError(missing)

        now = datetime.now(UTC)
        existing = await self._connections.get_by_owner(info.login)
        connection = GitHubConnection(
            id=existing.id if existing else uuid4(),
            owner=info.login,
            owner_type=info.owner_type,
            encrypted_token=self._cipher.encrypt(token),
            token_hint=token[-4:],
            permissions=sorted(info.permissions),
            created_at=existing.created_at if existing else now,
            updated_at=now,
        )
        await self._connections.save(connection)
        return _view(connection)

    async def list_connections(self) -> list[ConnectionView]:
        return [_view(c) for c in await self._connections.list_all()]

    async def test(self, connection_id: UUID) -> dict[str, object]:
        """On-demand health check: auth + rate limit (spec: github-connection)."""
        connection = await self._connections.get(connection_id)
        if connection is None:
            raise UnknownResourceError(f"connection {connection_id} not found")
        token = self._cipher.decrypt(connection.encrypted_token)
        try:
            rate = await self._github.get_rate_limit(token)
        except GitHubAuthError:
            connection.mark_broken()
            connection.updated_at = datetime.now(UTC)
            await self._connections.save(connection)
            return {"ok": False, "status": connection.status.value}
        if connection.status.value == "broken":
            connection.mark_active()
            connection.updated_at = datetime.now(UTC)
            await self._connections.save(connection)
        return {
            "ok": True,
            "status": connection.status.value,
            "permissions": connection.permissions,
            "rate_limit": rate,
        }

    async def delete(self, connection_id: UUID) -> None:
        """Destroy the credential. Indexed data stays; future syncs stop."""
        connection = await self._connections.get(connection_id)
        if connection is None:
            raise UnknownResourceError(f"connection {connection_id} not found")
        await self._connections.delete(connection_id)

    async def credential_for(self, connection_id: UUID) -> str:
        """Decrypted token for internal sync use only — never exposed by the API."""
        connection = await self._connections.get(connection_id)
        if connection is None:
            raise UnknownResourceError(f"connection {connection_id} not found")
        return self._cipher.decrypt(connection.encrypted_token)
