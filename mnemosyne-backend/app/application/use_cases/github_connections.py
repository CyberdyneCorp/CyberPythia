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
from app.domain.ports.github_app_port import GitHubAppError, GitHubAppPort
from app.domain.ports.github_port import GitHubAuthError, GitHubPort
from app.domain.ports.persistence_ports import ConnectionPort
from app.domain.value_objects.enums import ConnectionKind


class TokenCipher(Protocol):
    def encrypt(self, plaintext: str) -> bytes: ...

    def decrypt(self, ciphertext: bytes) -> str: ...


@dataclass(frozen=True, slots=True)
class ConnectionView:
    """What the API is allowed to expose — never the credential (spec: github-connection)."""

    id: UUID
    owner: str
    owner_type: str
    kind: str
    token_hint: str
    permissions: list[str]
    status: str
    installation_id: str | None = None


def _view(connection: GitHubConnection) -> ConnectionView:
    return ConnectionView(
        id=connection.id,
        owner=connection.owner,
        owner_type=connection.owner_type,
        kind=connection.kind.value,
        token_hint=connection.token_hint,
        permissions=list(connection.permissions),
        status=connection.status.value,
        installation_id=connection.installation_id,
    )


class GitHubConnectionUseCases:
    def __init__(
        self,
        connections: ConnectionPort,
        github: GitHubPort,
        cipher: TokenCipher,
        app_auth: GitHubAppPort | None = None,
    ) -> None:
        self._connections = connections
        self._github = github
        self._cipher = cipher
        self._app_auth = app_auth

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

    async def connect_app(
        self,
        app_id: str,
        installation_id: str,
        private_key_pem: str,
        webhook_secret: str,
    ) -> ConnectionView:
        """Register a GitHub App installation; validate by minting a token."""
        if self._app_auth is None:
            raise InvalidCredentialError("GitHub App support is not configured")
        try:
            token = await self._app_auth.installation_token(
                app_id, installation_id, private_key_pem
            )
            info = await self._github.validate_token(token)
        except (GitHubAppError, GitHubAuthError) as exc:
            raise InvalidCredentialError(str(exc)) from exc

        now = datetime.now(UTC)
        existing = await self._connections.get_by_owner(info.login)
        connection = GitHubConnection(
            id=existing.id if existing else uuid4(),
            owner=info.login,
            owner_type=info.owner_type,
            kind=ConnectionKind.GITHUB_APP,
            app_id=app_id,
            installation_id=installation_id,
            encrypted_private_key=self._cipher.encrypt(private_key_pem),
            encrypted_webhook_secret=self._cipher.encrypt(webhook_secret),
            permissions=sorted(info.permissions),
            created_at=existing.created_at if existing else now,
            updated_at=now,
        )
        await self._connections.save(connection)
        return _view(connection)

    async def _token_for(self, connection: GitHubConnection) -> str:
        """Resolve a connection to a usable GitHub token (design D1)."""
        if connection.kind is ConnectionKind.GITHUB_APP:
            if self._app_auth is None:
                raise InvalidCredentialError("GitHub App support is not configured")
            assert connection.app_id and connection.installation_id
            assert connection.encrypted_private_key is not None
            return await self._app_auth.installation_token(
                connection.app_id,
                connection.installation_id,
                self._cipher.decrypt(connection.encrypted_private_key),
            )
        assert connection.encrypted_token is not None
        return self._cipher.decrypt(connection.encrypted_token)

    async def webhook_secret_for_installation(self, installation_id: str) -> str | None:
        for c in await self._connections.list_all():
            if (
                c.kind is ConnectionKind.GITHUB_APP
                and c.installation_id == installation_id
                and c.encrypted_webhook_secret is not None
            ):
                return self._cipher.decrypt(c.encrypted_webhook_secret)
        return None

    async def list_connections(self) -> list[ConnectionView]:
        return [_view(c) for c in await self._connections.list_all()]

    async def test(self, connection_id: UUID) -> dict[str, object]:
        """On-demand health check: auth + rate limit (spec: github-connection)."""
        connection = await self._connections.get(connection_id)
        if connection is None:
            raise UnknownResourceError(f"connection {connection_id} not found")
        try:
            token = await self._token_for(connection)
        except (InvalidCredentialError, GitHubAppError):
            connection.mark_broken()
            connection.updated_at = datetime.now(UTC)
            await self._connections.save(connection)
            return {"ok": False, "status": connection.status.value}
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
        """Usable token for internal sync use only — never exposed by the API."""
        connection = await self._connections.get(connection_id)
        if connection is None:
            raise UnknownResourceError(f"connection {connection_id} not found")
        return await self._token_for(connection)
