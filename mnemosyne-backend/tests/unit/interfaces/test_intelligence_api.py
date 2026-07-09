"""Interface tests for the engineering-intelligence REST endpoints + MCP tools."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastmcp import Client

from app.interfaces.mcp.server import build_mcp
from tests.unit.interfaces.test_api_endpoints import build_fake_container, seed_repo, user
from tests.unit.interfaces.test_mcp_server import entitled_caller, payload, rejecting_caller

NOW = datetime(2026, 7, 7, tzinfo=UTC)

_METRICS = dict(
    issue_metrics={"open_count": 5, "closed_count": 20, "median_resolution_seconds": 172800.0,
                   "stale_issues": [], "by_label": {"bug": 2}},
    pr_metrics={"merged_count": 10, "open_count": 2, "median_time_to_merge_seconds": 86400.0,
                "merge_rate": 0.9, "size_distribution": {"S": 6}, "stale_prs": [],
                "by_reviewer": {"alice": 6, "bob": 2}},
    summary={"has_readme": True, "has_docs": True, "has_openspec": True,
             "documents": 3, "openspec_changes": 1},
)


async def _seed_scored(container):
    repo = await seed_repo(container)
    await container.metrics_store.save(repo.id, computed_at=NOW.isoformat(), **_METRICS)
    return repo


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


class TestIntelligenceRest:
    async def test_health_endpoint(self, client, container):
        repo = await _seed_scored(container)
        async with client:
            r = await client.get(
                f"/api/v1/intelligence/repositories/{repo.id}/health", headers=user()
            )
        assert r.status_code == 200
        body = r.json()
        assert body["has_data"] is True
        assert body["grade"] is not None
        assert {c["name"] for c in body["components"]} >= {"documentation", "delivery"}

    async def test_portfolio_endpoint(self, client, container):
        await _seed_scored(container)
        async with client:
            r = await client.get("/api/v1/intelligence/portfolio", headers=user())
        assert r.status_code == 200
        body = r.json()
        assert body["total_repositories"] == 1
        assert body["scored"] == 1
        assert len(body["leaderboard"]) == 1

    async def test_portfolio_org_scoped(self, client, container):
        repo = await _seed_scored(container)  # owner from seed_repo
        owner = str(repo.full_name).split("/")[0]
        async with client:
            match = await client.get(
                f"/api/v1/intelligence/portfolio?organization={owner}", headers=user()
            )
            miss = await client.get(
                "/api/v1/intelligence/portfolio?organization=nonexistent", headers=user()
            )
        assert match.json()["total_repositories"] == 1
        assert miss.json()["total_repositories"] == 0

    async def test_organization_intelligence_endpoint(self, client, container):
        repo = await _seed_scored(container)
        owner = str(repo.full_name).split("/")[0]
        async with client:
            r = await client.get(
                f"/api/v1/intelligence/organizations/{owner}/intelligence", headers=user()
            )
        assert r.status_code == 200
        body = r.json()
        assert body["organization"] == owner
        assert body["total_repositories"] == 1
        assert "grade_distribution" in body and "average_health" in body

    @pytest.mark.parametrize(
        "path", ["health", "delivery", "backlog", "review-bottlenecks",
                 "maintenance-risk", "onboarding"]
    )
    async def test_unknown_repo_404(self, client, path):
        async with client:
            r = await client.get(
                f"/api/v1/intelligence/repositories/{uuid4()}/{path}", headers=user()
            )
        assert r.status_code == 404

    async def test_missing_entitlement_403(self, client, container):
        repo = await _seed_scored(container)
        async with client:
            r = await client.get(
                f"/api/v1/intelligence/repositories/{repo.id}/delivery",
                headers={"Authorization": "Bearer unentitled-token"},
            )
        assert r.status_code == 403

    async def test_disabled_repo_intelligence_404(self, client, container):
        # a repo with persisted metrics but now un-indexed must not surface its data
        repo = await _seed_scored(container)
        repo.enabled = False
        await container.repositories.save(repo)
        async with client:
            r = await client.get(
                f"/api/v1/intelligence/repositories/{repo.id}/health", headers=user()
            )
        assert r.status_code == 404

    async def test_compare_endpoint(self, client, container):
        repo = await _seed_scored(container)
        async with client:
            r = await client.post(
                "/api/v1/intelligence/compare",
                json={"repository_ids": [str(repo.id)]}, headers=user(),
            )
        assert r.status_code == 200
        assert len(r.json()["comparison"]) == 1

    @pytest.mark.parametrize(
        "path", ["backlog", "review-bottlenecks", "maintenance-risk", "onboarding"]
    )
    async def test_per_repo_endpoints(self, client, container, path):
        repo = await _seed_scored(container)
        async with client:
            r = await client.get(
                f"/api/v1/intelligence/repositories/{repo.id}/{path}", headers=user()
            )
        assert r.status_code == 200


class TestIntelligenceMcp:
    @pytest.fixture
    def mcp(self, container):
        return build_mcp(container, authenticate=entitled_caller)

    async def test_health_tool(self, mcp, container):
        await _seed_scored(container)
        async with Client(mcp) as c:
            result = await c.call_tool(
                "mnemosyne_get_repository_health", {"full_name": "cyberdyne/a"}
            )
        body = payload(result)
        assert body["has_data"] is True and body["grade"]

    async def test_portfolio_tool(self, mcp, container):
        await _seed_scored(container)
        async with Client(mcp) as c:
            result = await c.call_tool("mnemosyne_get_portfolio_overview", {})
        body = payload(result)
        assert body["scored"] == 1

    async def test_insufficient_data_is_structured(self, mcp, container):
        await seed_repo(container)  # enabled but no metrics row
        async with Client(mcp) as c:
            result = await c.call_tool(
                "mnemosyne_get_repository_health", {"full_name": "cyberdyne/a"}
            )
        body = payload(result)
        # synced repo with no metrics row -> health has_data False, not an error
        assert body["has_data"] is False and body["overall"] is None

    async def test_disabled_repo_not_indexed(self, mcp, container):
        repo = await _seed_scored(container)  # cyberdyne/a with metrics
        repo.enabled = False
        await container.repositories.save(repo)
        async with Client(mcp) as c:
            result = await c.call_tool(
                "mnemosyne_get_repository_health", {"full_name": "cyberdyne/a"}
            )
        assert payload(result)["error"]["code"] == "unknown_repository"

    async def test_unknown_repo_structured_error(self, mcp):
        async with Client(mcp) as c:
            result = await c.call_tool(
                "mnemosyne_get_maintenance_risk", {"full_name": "cyberdyne/missing"}
            )
        body = payload(result)
        assert body["error"]["code"] == "unknown_repository"

    async def test_unauthenticated_rejected(self, container):
        from fastmcp.exceptions import ToolError

        mcp = build_mcp(container, authenticate=rejecting_caller)
        with pytest.raises(ToolError):
            async with Client(mcp) as c:
                await c.call_tool("mnemosyne_get_portfolio_overview", {})

    @pytest.mark.parametrize(
        "tool",
        [
            "mnemosyne_get_delivery_metrics",
            "mnemosyne_get_backlog_metrics",
            "mnemosyne_get_review_bottlenecks",
            "mnemosyne_get_maintenance_risk",
            "mnemosyne_generate_onboarding_summary",
        ],
    )
    async def test_per_repo_tools(self, mcp, container, tool):
        await _seed_scored(container)
        async with Client(mcp) as c:
            result = await c.call_tool(tool, {"full_name": "cyberdyne/a"})
        assert payload(result)  # structured, non-empty

    async def test_per_repo_tool_unknown_repo(self, mcp):
        async with Client(mcp) as c:
            result = await c.call_tool(
                "mnemosyne_get_delivery_metrics", {"full_name": "cyberdyne/missing"}
            )
        assert payload(result)["error"]["code"] == "unknown_repository"

    async def test_compare_tool(self, mcp, container):
        await _seed_scored(container)
        async with Client(mcp) as c:
            result = await c.call_tool(
                "mnemosyne_compare_repositories", {"full_names": ["cyberdyne/a"]}
            )
        assert len(payload(result)["comparison"]) == 1

    async def test_compare_tool_unknown_repo(self, mcp):
        async with Client(mcp) as c:
            result = await c.call_tool(
                "mnemosyne_compare_repositories", {"full_names": ["cyberdyne/missing"]}
            )
        assert payload(result)["error"]["code"] == "unknown_repository"


class TestCrossRepoRest:
    async def test_search_issues(self, client, container):
        from app.domain.entities.issue import Issue
        from app.domain.value_objects.enums import IssueState

        repo = await seed_repo(container)
        await container.issues.save_many([
            Issue(id=uuid4(), repository_id=repo.id, github_issue_id=1, number=7,
                  title="server crash on boot", body="b", state=IssueState.OPEN,
                  author="a", labels=["bug"], created_at=NOW, updated_at=NOW),
        ])
        async with client:
            r = await client.get(
                "/api/v1/intelligence/search?query=server&kind=issues", headers=user()
            )
        assert r.status_code == 200
        results = r.json()["results"]
        assert results and results[0]["number"] == 7

    async def test_search_invalid_kind_422(self, client):
        async with client:
            r = await client.get(
                "/api/v1/intelligence/search?query=x&kind=bogus", headers=user()
            )
        assert r.status_code == 422

    async def test_stale_issues_endpoint(self, client, container):
        from datetime import timedelta

        from app.domain.entities.issue import Issue
        from app.domain.value_objects.enums import IssueState

        repo = await seed_repo(container)
        old = datetime.now(UTC) - timedelta(days=90)
        await container.issues.save_many([
            Issue(id=uuid4(), repository_id=repo.id, github_issue_id=2, number=3,
                  title="ancient", body="b", state=IssueState.OPEN, author="a",
                  labels=[], created_at=old, updated_at=old),
        ])
        async with client:
            r = await client.get("/api/v1/intelligence/stale-issues", headers=user())
        assert r.status_code == 200
        assert r.json()["stale"][0]["number"] == 3

    async def test_recent_activity_endpoint(self, client, container):
        await seed_repo(container)
        async with client:
            r = await client.get("/api/v1/intelligence/recent-activity", headers=user())
        assert r.status_code == 200
        body = r.json()
        assert set(body) >= {"recently_synced", "recent_issues", "recent_pull_requests"}

    async def test_find_repositories_endpoint(self, client, container):
        repo = await seed_repo(container)  # cyberdyne/a
        name = repo.full_name.name
        async with client:
            r = await client.get(
                f"/api/v1/repos/find?query={name}", headers=user()
            )
        assert r.status_code == 200
        assert any(x["full_name"] == str(repo.full_name) for x in r.json()["repositories"])
