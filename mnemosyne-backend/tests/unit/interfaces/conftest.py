"""Interface-test fixtures: FastAPI app with fake auth/audit wiring."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.domain.ports.auth_port import AuthUnavailableError, TokenInvalidError
from app.domain.value_objects.identity import CallerIdentity
from app.interfaces.api.errors import register_error_handlers

# Tokens understood by the FakeAuthPort
TOKENS = {
    "admin-token": CallerIdentity(
        subject="admin-1", is_admin=True, entitlements=frozenset({"mnemosyne"})
    ),
    "scope-admin-token": CallerIdentity(
        subject="scope-admin-1",
        scopes=frozenset({"mnemosyne:admin"}),
        entitlements=frozenset({"mnemosyne"}),
    ),
    "user-token": CallerIdentity(subject="user-1", entitlements=frozenset({"mnemosyne"})),
    # restricted to the `cyberdyne` org via a plan-qualified entitlement
    "scoped-token": CallerIdentity(
        subject="scoped-1", entitlements=frozenset({"mnemosyne:cyberdyne"})
    ),
    "unentitled-token": CallerIdentity(subject="other-1", entitlements=frozenset({"otherapp"})),
    "agent-token": CallerIdentity(
        subject="agent-1", client_id="agent-client", entitlements=frozenset({"mnemosyne"})
    ),
}


class FakeAuthPort:
    async def verify(self, token: str) -> CallerIdentity:
        if token == "auth-down":
            raise AuthUnavailableError("down")
        identity = TOKENS.get(token)
        if identity is None:
            raise TokenInvalidError("invalid")
        return identity


class FakeAuditPort:
    def __init__(self):
        self.records = []

    async def record(self, entry):
        self.records.append(entry)

    async def list_recent(self, limit=100):
        return self.records[-limit:]


class FakeApiKeyPort:
    def __init__(self):
        self.keys = {}  # id -> ApiKey

    async def save(self, key):
        self.keys[key.id] = key

    async def get_by_hash(self, key_hash):
        return next((k for k in self.keys.values() if k.key_hash == key_hash), None)

    async def list_all(self):
        return sorted(self.keys.values(), key=lambda k: k.created_at, reverse=True)

    async def revoke(self, key_id):
        key = self.keys.get(key_id)
        if key is None:
            return False
        key.revoked = True
        return True

    async def delete(self, key_id):
        return self.keys.pop(key_id, None) is not None


@pytest.fixture
def audit_port():
    return FakeAuditPort()


def wire_test_auth(app: FastAPI, audit_port: FakeAuditPort) -> None:
    from app.application.audit import AuditService

    app.state.auth_port = FakeAuthPort()
    app.state.audit_service = AuditService(audit_port)
    register_error_handlers(app)


@pytest.fixture
def make_client(audit_port):
    """Factory: build an AsyncClient around a FastAPI app wired with fakes."""

    def _make(app: FastAPI) -> AsyncClient:
        wire_test_auth(app, audit_port)
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    return _make
