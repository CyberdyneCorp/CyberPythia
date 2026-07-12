"""Auth matrix tests for the security dependencies (spec: auth)."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.application.audit import AuditService
from app.domain.ports.auth_port import TokenInvalidError
from app.domain.value_objects.identity import CallerIdentity
from app.interfaces.api.errors import register_error_handlers
from app.interfaces.api.security import AdminCaller, EntitledCaller, WriterCaller


@pytest.fixture
def app() -> FastAPI:
    app = FastAPI()

    @app.get("/data")
    async def data(caller: EntitledCaller):
        return {"subject": caller.subject}

    @app.post("/write-op")
    async def write_op(caller: WriterCaller):
        return {"subject": caller.subject}

    @app.post("/admin-op")
    async def admin_op(caller: AdminCaller):
        return {"subject": caller.subject}

    return app


async def test_writer_endpoint_rejects_read_only_caller(app, make_client, audit_port):
    async with make_client(app) as client:
        response = await client.post(
            "/write-op", headers={"Authorization": "Bearer readonly-token"}
        )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "read_only"
    assert audit_port.records[-1].outcome == "denied"


async def test_writer_endpoint_allows_normal_caller(app, make_client):
    async with make_client(app) as client:
        response = await client.post(
            "/write-op", headers={"Authorization": "Bearer user-token"}
        )
    assert response.status_code == 200


class _RevocationAuthPort:
    """JWKS path trusts embedded claims; forced introspection reports revocation."""

    async def verify(self, token: str, *, force_introspection: bool = False):
        if force_introspection:
            raise TokenInvalidError("revoked")
        return CallerIdentity(
            subject="admin-1", is_admin=True, entitlements=frozenset({"mnemosyne"})
        )


async def test_admin_forces_introspection_and_rejects_revoked_token(audit_port):
    # CWE-613: an admin request with a structurally-valid, entitlement-bearing JWT
    # that introspection reports revoked must be rejected on the admin path.
    app = FastAPI()

    @app.post("/admin-op")
    async def admin_op(caller: AdminCaller):
        return {"subject": caller.subject}

    app.state.auth_port = _RevocationAuthPort()
    app.state.audit_service = AuditService(audit_port)
    register_error_handlers(app)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/admin-op", headers={"Authorization": "Bearer revoked-admin"}
        )
    assert response.status_code == 401


async def test_missing_token_401(app, make_client):
    async with make_client(app) as client:
        response = await client.get("/data")
    assert response.status_code == 401
    body = response.json()["error"]
    assert body["code"] == "unauthenticated"
    assert "correlation_id" in body


async def test_invalid_token_401_does_not_reveal_reason(app, make_client, audit_port):
    async with make_client(app) as client:
        response = await client.get("/data", headers={"Authorization": "Bearer bogus"})
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "invalid token"
    assert audit_port.records[-1].outcome == "denied"


async def test_unentitled_caller_403_with_entitlement_code(app, make_client, audit_port):
    async with make_client(app) as client:
        response = await client.get("/data", headers={"Authorization": "Bearer unentitled-token"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "missing_entitlement"
    assert audit_port.records[-1].outcome == "denied"


async def test_entitled_user_ok(app, make_client):
    async with make_client(app) as client:
        response = await client.get("/data", headers={"Authorization": "Bearer user-token"})
    assert response.status_code == 200
    assert response.json() == {"subject": "user-1"}


async def test_entitled_agent_service_token_ok(app, make_client):
    async with make_client(app) as client:
        response = await client.get("/data", headers={"Authorization": "Bearer agent-token"})
    assert response.status_code == 200


async def test_non_admin_cannot_admin(app, make_client, audit_port):
    async with make_client(app) as client:
        response = await client.post("/admin-op", headers={"Authorization": "Bearer user-token"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "admin_required"
    assert audit_port.records[-1].outcome == "denied"


@pytest.mark.parametrize("token", ["admin-token", "scope-admin-token"])
async def test_admin_paths(app, make_client, token):
    async with make_client(app) as client:
        response = await client.post("/admin-op", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200


async def test_auth_plane_down_503(app, make_client):
    async with make_client(app) as client:
        response = await client.get("/data", headers={"Authorization": "Bearer auth-down"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "upstream_unavailable"
