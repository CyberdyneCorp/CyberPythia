"""Interface tests for organization repository filtering (REST + MCP)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastmcp import Client

from app.domain.entities.repository import Repository
from app.domain.value_objects.enums import IndexingMode, RepositoryVisibility
from app.domain.value_objects.full_name import RepositoryFullName
from app.interfaces.mcp.server import build_mcp
from tests.unit.interfaces.test_api_endpoints import build_fake_container, user
from tests.unit.interfaces.test_mcp_server import entitled_caller, payload, rejecting_caller

NOW = datetime(2026, 7, 8, tzinfo=UTC)


def repo(owner, name, *, enabled=True) -> Repository:
    return Repository(
        id=uuid4(), connection_id=uuid4(), github_id=hash((owner, name)) % 100000,
        full_name=RepositoryFullName(f"{owner}/{name}"), description="d",
        visibility=RepositoryVisibility.PRIVATE, default_branch="main",
        primary_language="Python", archived=False, github_updated_at=NOW,
        enabled=enabled, indexing_mode=IndexingMode.PROJECT_INTELLIGENCE,
        last_synced_at=NOW if enabled else None,
    )


async def _seed(container):
    for r in [
        repo("CyberdyneCorp", "auth"), repo("CyberdyneCorp", "pythia"),
        repo("aminitech", "x", enabled=False), repo("EpicGames", "ue"),
    ]:
        await container.repositories.save(r)


@pytest.fixture
def container():
    return build_fake_container()


@pytest.fixture
def client(container):
    from httpx import ASGITransport, AsyncClient

    from app.main import create_app

    app = create_app(container)
    app.state.auth_port = container.auth_port
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


class TestRestFilter:
    async def test_filter_by_organization(self, client, container):
        await _seed(container)
        async with client:
            r = await client.get(
                "/api/v1/repos?organization=cyberdynecorp&page_size=50", headers=user()
            )
        assert r.status_code == 200
        names = [i["full_name"] for i in r.json()["items"]]
        assert set(names) == {"CyberdyneCorp/auth", "CyberdyneCorp/pythia"}

    async def test_no_filter_returns_all_orgs(self, client, container):
        await _seed(container)
        async with client:
            r = await client.get("/api/v1/repos?page_size=50", headers=user())
        owners = {i["full_name"].split("/")[0] for i in r.json()["items"]}
        assert owners == {"CyberdyneCorp", "aminitech", "EpicGames"}


class TestMcpTools:
    @pytest.fixture
    def mcp(self, container):
        return build_mcp(container, authenticate=entitled_caller)

    async def test_list_organizations(self, mcp, container):
        await _seed(container)
        async with Client(mcp) as c:
            result = await c.call_tool("mnemosyne_list_organizations", {})
        orgs = {o["login"]: o for o in payload(result)}
        assert set(orgs) == {"CyberdyneCorp", "aminitech", "EpicGames"}
        assert orgs["CyberdyneCorp"]["total_repos"] == 2
        assert orgs["CyberdyneCorp"]["indexed_repos"] == 2
        assert orgs["aminitech"]["indexed_repos"] == 0

    async def test_list_organization_repositories(self, mcp, container):
        await _seed(container)
        async with Client(mcp) as c:
            result = await c.call_tool(
                "mnemosyne_list_organization_repositories", {"organization": "cyberdynecorp"}
            )
        body = payload(result)
        assert {r["full_name"] for r in body} == {"CyberdyneCorp/auth", "CyberdyneCorp/pythia"}
        assert all(r["indexed"] for r in body)

    async def test_unauthenticated_rejected(self, container):
        from fastmcp.exceptions import ToolError

        mcp = build_mcp(container, authenticate=rejecting_caller)
        with pytest.raises(ToolError):
            async with Client(mcp) as c:
                await c.call_tool("mnemosyne_list_organizations", {})
