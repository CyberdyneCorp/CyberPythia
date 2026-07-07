"""Interface tests for the PM/PO delivery REST endpoints + MCP tools."""

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from fastmcp import Client

from app.domain.entities.issue import Issue
from app.domain.entities.metrics_snapshot import MetricsSnapshot
from app.domain.value_objects.enums import IssueState
from app.interfaces.mcp.server import build_mcp
from tests.unit.interfaces.test_api_endpoints import build_fake_container, seed_repo, user
from tests.unit.interfaces.test_mcp_server import entitled_caller, payload

NOW = datetime(2026, 7, 7, tzinfo=UTC)


async def _seed_delivery(container, repo):
    # closed issues (for percentiles) + snapshots (for trend/forecast)
    for n in range(1, 4):
        container.issues.items[(repo.id, n)] = Issue(
            id=uuid4(), repository_id=repo.id, github_issue_id=n, number=n,
            title="t", body=None, state=IssueState.CLOSED, author="a",
            labels=["bug"] if n == 1 else ["feature"], assignees=["a"], milestone=None,
            created_at=NOW - timedelta(days=n + 1), updated_at=NOW, closed_at=NOW,
            comments_count=0,
        )
    for day, closed, opened in [(1, 5, 20), (2, 12, 9)]:
        await container.metrics_history.record(
            MetricsSnapshot(
                repository_id=repo.id, captured_on=date(2026, 7, day), captured_at=NOW,
                open_issues=opened, closed_issues=closed, open_prs=0, merged_prs=0,
                median_cycle_seconds=None, health_overall=80.0,
            )
        )


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


class TestDeliveryRest:
    async def test_flow_endpoint(self, client, container):
        repo = await seed_repo(container)
        await _seed_delivery(container, repo)
        async with client:
            r = await client.get(
                f"/api/v1/intelligence/repositories/{repo.id}/flow", headers=user()
            )
        assert r.status_code == 200
        assert r.json()["has_data"] is True
        assert r.json()["resolution_seconds"]["n"] == 3

    async def test_work_mix_endpoint(self, client, container):
        repo = await seed_repo(container)
        await _seed_delivery(container, repo)
        async with client:
            r = await client.get(
                f"/api/v1/intelligence/repositories/{repo.id}/work-mix", headers=user()
            )
        assert r.status_code == 200
        body = r.json()
        assert body["distribution"]["bug"] == 1
        assert body["bug_ratio"] == pytest.approx(1 / 3)

    async def test_forecast_endpoint(self, client, container):
        repo = await seed_repo(container)
        await _seed_delivery(container, repo)
        async with client:
            r = await client.get(
                f"/api/v1/intelligence/repositories/{repo.id}/forecast", headers=user()
            )
        assert r.status_code == 200
        assert r.json()["projected_clear_date"] is not None

    async def test_scorecard_endpoint(self, client, container):
        repo = await seed_repo(container)
        await _seed_delivery(container, repo)
        async with client:
            r = await client.get("/api/v1/intelligence/delivery-scorecard", headers=user())
        assert r.status_code == 200
        assert len(r.json()["scorecard"]) == 1

    @pytest.mark.parametrize(
        "path", ["flow", "throughput", "forecast", "work-mix", "quality",
                 "milestones", "team-load"]
    )
    async def test_unknown_repo_404(self, client, path):
        async with client:
            r = await client.get(
                f"/api/v1/intelligence/repositories/{uuid4()}/{path}", headers=user()
            )
        assert r.status_code == 404

    async def test_missing_entitlement_403(self, client, container):
        repo = await seed_repo(container)
        async with client:
            r = await client.get(
                f"/api/v1/intelligence/repositories/{repo.id}/flow",
                headers={"Authorization": "Bearer unentitled-token"},
            )
        assert r.status_code == 403


class TestDeliveryMcp:
    @pytest.fixture
    def mcp(self, container):
        return build_mcp(container, authenticate=entitled_caller)

    @pytest.mark.parametrize(
        "tool",
        [
            "mnemosyne_get_flow_metrics",
            "mnemosyne_get_throughput_trend",
            "mnemosyne_get_backlog_forecast",
            "mnemosyne_get_work_mix",
            "mnemosyne_get_quality_signals",
            "mnemosyne_get_team_load",
            "mnemosyne_get_milestone_progress",
        ],
    )
    async def test_delivery_tools(self, mcp, container, tool):
        repo = await seed_repo(container)
        await _seed_delivery(container, repo)
        async with Client(mcp) as c:
            result = await c.call_tool(tool, {"full_name": "cyberdyne/a"})
        assert payload(result)

    async def test_scorecard_tool(self, mcp, container):
        repo = await seed_repo(container)
        await _seed_delivery(container, repo)
        async with Client(mcp) as c:
            result = await c.call_tool("mnemosyne_get_delivery_scorecard", {})
        assert len(payload(result)["scorecard"]) == 1

    async def test_tool_unknown_repo(self, mcp):
        async with Client(mcp) as c:
            result = await c.call_tool(
                "mnemosyne_get_flow_metrics", {"full_name": "cyberdyne/missing"}
            )
        assert payload(result)["error"]["code"] == "unknown_repository"
