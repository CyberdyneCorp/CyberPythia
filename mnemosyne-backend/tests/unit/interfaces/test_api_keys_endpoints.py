"""Interface tests for API key management + end-to-end key authentication."""

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.domain.services.api_key_factory import API_KEY_PREFIX
from app.infrastructure.auth.api_key_auth import ApiKeyAuthAdapter
from app.main import create_app
from tests.unit.interfaces.conftest import FakeAuthPort
from tests.unit.interfaces.test_api_endpoints import admin, build_fake_container, user


@pytest.fixture
def container():
    return build_fake_container()


@pytest.fixture
def client(container):
    app = create_app(container)
    app.state.auth_port = container.auth_port
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


class TestManagement:
    async def test_create_returns_plaintext_once(self, client):
        async with client:
            r = await client.post(
                "/api/v1/api-keys",
                json={"label": "claude-agent", "expires_in_days": 30},
                headers=admin(),
            )
        assert r.status_code == 201
        body = r.json()
        assert body["key"].startswith(API_KEY_PREFIX)
        assert body["label"] == "claude-agent"
        assert body["expires_at"] is not None
        assert body["revoked"] is False

    async def test_create_without_expiry(self, client):
        async with client:
            r = await client.post(
                "/api/v1/api-keys", json={"label": "perm"}, headers=admin()
            )
        assert r.status_code == 201 and r.json()["expires_at"] is None

    async def test_create_unscoped_key_reports_null_org_scope(self, client):
        async with client:
            r = await client.post("/api/v1/api-keys", json={"label": "a"}, headers=admin())
        assert r.status_code == 201
        assert r.json()["allowed_organizations"] is None  # unrestricted (default)

    async def test_create_org_scoped_key_echoes_normalised_orgs(self, client):
        async with client:
            r = await client.post(
                "/api/v1/api-keys",
                json={"label": "scoped", "allowed_organizations": ["CyberDyne"]},
                headers=admin(),
            )
        assert r.status_code == 201
        assert r.json()["allowed_organizations"] == ["cyberdyne"]  # lower-cased

    async def test_list_omits_plaintext_and_hash(self, client):
        async with client:
            await client.post("/api/v1/api-keys", json={"label": "a"}, headers=admin())
            r = await client.get("/api/v1/api-keys", headers=admin())
        assert r.status_code == 200
        row = r.json()[0]
        assert "key" not in row and "key_hash" not in row
        assert row["label"] == "a" and row["prefix"].startswith(API_KEY_PREFIX)

    async def test_revoke_keeps_record(self, client):
        async with client:
            created = (
                await client.post("/api/v1/api-keys", json={"label": "a"}, headers=admin())
            ).json()
            r = await client.post(f"/api/v1/api-keys/{created['id']}/revoke", headers=admin())
            listed = (await client.get("/api/v1/api-keys", headers=admin())).json()
        assert r.status_code == 204
        assert listed[0]["revoked"] is True  # still listed, marked revoked

    async def test_delete_removes_key(self, client):
        async with client:
            created = (
                await client.post("/api/v1/api-keys", json={"label": "gone"}, headers=admin())
            ).json()
            r = await client.delete(f"/api/v1/api-keys/{created['id']}", headers=admin())
            listed = (await client.get("/api/v1/api-keys", headers=admin())).json()
        assert r.status_code == 204
        assert all(k["id"] != created["id"] for k in listed)  # removed from the list

    async def test_revoke_unknown_404(self, client):
        async with client:
            r = await client.post(f"/api/v1/api-keys/{uuid4()}/revoke", headers=admin())
        assert r.status_code == 404

    async def test_delete_unknown_404(self, client):
        async with client:
            r = await client.delete(f"/api/v1/api-keys/{uuid4()}", headers=admin())
        assert r.status_code == 404

    async def test_create_requires_admin(self, client):
        async with client:
            r = await client.post("/api/v1/api-keys", json={"label": "x"}, headers=user())
        assert r.status_code == 403

    async def test_list_requires_admin(self, client):
        async with client:
            r = await client.get("/api/v1/api-keys", headers=user())
        assert r.status_code == 403

    async def test_delete_requires_admin(self, client):
        async with client:
            created = (
                await client.post("/api/v1/api-keys", json={"label": "a"}, headers=admin())
            ).json()
            r = await client.delete(f"/api/v1/api-keys/{created['id']}", headers=user())
        assert r.status_code == 403


class TestKeyAuthenticates:
    """A generated key authenticates against a protected endpoint via the composite."""

    @pytest.fixture
    def client(self, container):
        app = create_app(container)
        # Real composite: API keys first, fake CyberdyneAuth fallback.
        app.state.auth_port = ApiKeyAuthAdapter(
            api_keys=container.api_keys, fallback=FakeAuthPort(), entitlement="mnemosyne"
        )
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    async def test_created_key_grants_read_access(self, client, container):
        created = await container.api_key_use_cases.create(
            label="agent", created_by="admin-1"
        )
        async with client:
            r = await client.get(
                "/api/v1/repos",
                headers={"Authorization": f"Bearer {created.plaintext}"},
            )
        assert r.status_code == 200

    async def test_revoked_key_denied(self, client, container):
        created = await container.api_key_use_cases.create(
            label="agent", created_by="admin-1"
        )
        await container.api_key_use_cases.revoke(created.key.id)
        async with client:
            r = await client.get(
                "/api/v1/repos",
                headers={"Authorization": f"Bearer {created.plaintext}"},
            )
        assert r.status_code == 401

    async def test_api_key_cannot_administer(self, client, container):
        created = await container.api_key_use_cases.create(
            label="agent", created_by="admin-1"
        )
        async with client:
            r = await client.post(
                "/api/v1/api-keys",
                json={"label": "nope"},
                headers={"Authorization": f"Bearer {created.plaintext}"},
            )
        assert r.status_code == 403  # entitled but not admin

    async def test_org_scoped_key_denied_cross_org_repos(self, client, container):
        """#64 (CWE-284): a key scoped to `cyberdyne` reads its own org's repos but
        not another org's — enforced through the shared org-scope choke point."""
        from tests.unit.interfaces.test_api_endpoints import seed_repo

        await seed_repo(container)  # cyberdyne/a
        await _seed_repo_in_org(container, "victim/b")
        created = await container.api_key_use_cases.create(
            label="scoped", created_by="admin-1", allowed_organizations=["cyberdyne"]
        )
        async with client:
            r = await client.get(
                "/api/v1/repos",
                headers={"Authorization": f"Bearer {created.plaintext}"},
            )
        assert r.status_code == 200
        owners = {row["full_name"].split("/")[0] for row in r.json()["items"]}
        assert owners == {"cyberdyne"}  # victim/b is invisible to the scoped key

    async def test_unscoped_key_sees_all_orgs(self, client, container):
        from tests.unit.interfaces.test_api_endpoints import seed_repo

        await seed_repo(container)  # cyberdyne/a
        await _seed_repo_in_org(container, "victim/b")
        created = await container.api_key_use_cases.create(
            label="unscoped", created_by="admin-1"
        )
        async with client:
            r = await client.get(
                "/api/v1/repos",
                headers={"Authorization": f"Bearer {created.plaintext}"},
            )
        assert r.status_code == 200
        owners = {row["full_name"].split("/")[0] for row in r.json()["items"]}
        assert owners == {"cyberdyne", "victim"}  # unrestricted key sees both


async def _seed_repo_in_org(container, full_name):
    from datetime import UTC, datetime

    from app.domain.entities.repository import Repository
    from app.domain.value_objects.enums import IndexingMode, RepositoryVisibility
    from app.domain.value_objects.full_name import RepositoryFullName

    now = datetime(2026, 7, 12, tzinfo=UTC)
    repo = Repository(
        id=uuid4(), connection_id=uuid4(), github_id=abs(hash(full_name)) % 99999,
        full_name=RepositoryFullName(full_name), description="d",
        visibility=RepositoryVisibility.PRIVATE, default_branch="main",
        primary_language="Python", archived=False, github_updated_at=now,
        enabled=True, indexing_mode=IndexingMode.PROJECT_INTELLIGENCE, last_synced_at=now,
    )
    await container.repositories.save(repo)
    return repo
