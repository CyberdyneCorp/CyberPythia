"""GitHub credential lifecycle use cases (spec: github-connection)."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
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
from app.domain.services.signed_state import sign_state, verify_state
from app.domain.value_objects.enums import ConnectionKind, ConnectionStatus


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
        *,
        public_api_base_url: str = "",
        github_web_base_url: str = "https://github.com",
        state_secret: str = "",
    ) -> None:
        self._connections = connections
        self._github = github
        self._cipher = cipher
        self._app_auth = app_auth
        self._api_base = public_api_base_url.rstrip("/")
        self._gh_web = github_web_base_url.rstrip("/")
        self._state_secret = state_secret

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

    # -- App manifest onboarding (one-click create + install) -----------------

    def build_app_manifest(
        self, organization: str, subject: str
    ) -> tuple[dict[str, object], str, str]:
        """Return (manifest, github_post_url, state) to hand off App creation."""
        expires = datetime.now(UTC) + timedelta(minutes=30)
        state = sign_state(
            self._state_secret, organization=organization, subject=subject, expires_at=expires
        )
        manifest: dict[str, object] = {
            "name": f"Mnemosyne-{organization}"[:34],  # GitHub App name cap
            "url": self._api_base,
            "hook_attributes": {"url": f"{self._api_base}/api/v1/webhooks/github", "active": True},
            "redirect_url": f"{self._api_base}/api/v1/github/app/manifest-callback",
            # state baked in so the post-install setup redirect can be verified too
            "setup_url": f"{self._api_base}/api/v1/github/app/setup?state={state}",
            "setup_on_update": False,
            "public": False,
            "default_permissions": {
                "contents": "read", "issues": "read",
                "pull_requests": "read", "metadata": "read",
            },
            # `installation` / `installation_repositories` are app-management meta
            # events GitHub always delivers — they are rejected if declared here.
            "default_events": [
                "push", "issues", "issue_comment", "pull_request",
                "pull_request_review", "pull_request_review_comment",
                "repository",
            ],
        }
        post_url = f"{self._gh_web}/organizations/{organization}/settings/apps/new?state={state}"
        return manifest, post_url, state

    async def complete_manifest(self, code: str, state: str) -> tuple[ConnectionView, str]:
        """Convert the manifest code → App credentials; persist a pending connection.

        Returns (view, install_url) — the caller redirects the admin to install.
        """
        if self._app_auth is None:
            raise InvalidCredentialError("GitHub App support is not configured")
        verify_state(self._state_secret, state)
        try:
            creds = await self._app_auth.convert_manifest_code(code)
        except GitHubAppError as exc:
            raise InvalidCredentialError(str(exc)) from exc
        now = datetime.now(UTC)
        existing = await self._connections.get_by_owner(creds.owner_login)
        connection = GitHubConnection(
            id=existing.id if existing else uuid4(),
            owner=creds.owner_login,
            owner_type="Organization",
            kind=ConnectionKind.GITHUB_APP,
            app_id=creds.app_id,
            encrypted_private_key=self._cipher.encrypt(creds.private_key_pem),
            encrypted_webhook_secret=self._cipher.encrypt(creds.webhook_secret),
            status=ConnectionStatus.PENDING_INSTALLATION,
            created_at=existing.created_at if existing else now,
            updated_at=now,
        )
        await self._connections.save(connection)
        return _view(connection), f"{creds.html_url}/installations/new"

    async def complete_setup(self, installation_id: str, state: str) -> ConnectionView:
        """Finalize a pending App connection once installed: attach + validate."""
        if self._app_auth is None:
            raise InvalidCredentialError("GitHub App support is not configured")
        payload = verify_state(self._state_secret, state)
        org = str(payload["org"])
        connection = await self._connections.get_by_owner(org)
        if connection is None or connection.kind is not ConnectionKind.GITHUB_APP:
            raise UnknownResourceError(f"no pending GitHub App connection for '{org}'")
        try:
            token = await self._app_auth.installation_token(
                connection.app_id or "",
                installation_id,
                self._cipher.decrypt(connection.encrypted_private_key or b""),
            )
            info = await self._github.validate_token(token)
        except (GitHubAppError, GitHubAuthError) as exc:
            connection.mark_broken()
            await self._connections.save(connection)
            raise InvalidCredentialError(str(exc)) from exc
        connection.installation_id = installation_id
        connection.permissions = sorted(info.permissions)
        connection.updated_at = datetime.now(UTC)
        connection.mark_active()
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
