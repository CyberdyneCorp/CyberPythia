"""Interface tests for the sync observability admin endpoints."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.domain.entities.sync_job import SyncJob
from app.domain.entities.sync_run import SyncRun
from app.domain.value_objects.enums import IndexingMode, SyncStatus, SyncStep
from tests.unit.interfaces.test_api_endpoints import admin, build_fake_container, seed_repo

NOW = datetime(2026, 7, 7, tzinfo=UTC)


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


def _run(**kw) -> SyncRun:
    base = dict(
        id=uuid4(), trigger="scheduler", started_at=NOW, finished_at=NOW,
        discovered=345, newly_enabled=2, skipped_archived=107,
        enqueued=238, skipped=1, failed=3,
    )
    base.update(kw)
    return SyncRun(**base)  # type: ignore[arg-type]


class TestSyncRuns:
    async def test_lists_recent_runs(self, client, container):
        container.sync_runs.runs.append(_run())
        async with client:
            r = await client.get("/api/v1/admin/sync-runs", headers=admin())
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 1
        assert body[0]["enqueued"] == 238 and body[0]["newly_enabled"] == 2

    async def test_non_admin_rejected(self, client):
        async with client:
            r = await client.get(
                "/api/v1/admin/sync-runs", headers={"Authorization": "Bearer user-token"}
            )
        assert r.status_code == 403


class TestSyncJobs:
    async def test_lists_jobs_with_repo_name_and_failure_reason(self, client, container):
        repo = await seed_repo(container)
        job = SyncJob(
            id=uuid4(), repository_id=repo.id, mode=IndexingMode.PROJECT_INTELLIGENCE,
            triggered_by="scheduler",
        )
        job.plan()
        job.start(NOW)
        job.record_step(
            SyncStep.ISSUES, SyncStatus.FAILED,
            error="GitHubRateLimitError: rate limited; resets in ~1800s (> 60.0s cap)",
        )
        job.finish(NOW)
        container.sync_jobs.items[job.id] = job
        async with client:
            r = await client.get("/api/v1/admin/sync-jobs", headers=admin())
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 1
        entry = body[0]
        assert entry["repository_full_name"] == "cyberdyne/a"
        assert entry["status"] == "failed"
        assert any("rate limited" in e for e in entry["errors"])

    async def test_non_admin_rejected(self, client):
        async with client:
            r = await client.get(
                "/api/v1/admin/sync-jobs", headers={"Authorization": "Bearer user-token"}
            )
        assert r.status_code == 403


class TestOrganizations:
    async def test_list_with_counts(self, client, container):
        repo = await seed_repo(container)  # cyberdyne/a, enabled=False by default
        repo.enabled = True
        await container.repositories.save(repo)
        await container.organizations.upsert_many(["cyberdyne"], default_enabled=True)
        async with client:
            r = await client.get("/api/v1/github/organizations", headers=admin())
        assert r.status_code == 200
        body = r.json()
        org = next(o for o in body if o["login"] == "cyberdyne")
        assert org["sync_enabled"] is True
        assert org["total_repos"] == 1 and org["enabled_repos"] == 1

    async def test_toggle_disable(self, client, container):
        await container.organizations.upsert_many(["cyberdyne"], default_enabled=True)
        async with client:
            r = await client.patch(
                "/api/v1/github/organizations/cyberdyne",
                json={"sync_enabled": False}, headers=admin(),
            )
        assert r.status_code == 200
        assert r.json()["sync_enabled"] is False
        assert await container.organizations.disabled_logins() == {"cyberdyne"}

    async def test_toggle_unknown_404(self, client):
        async with client:
            r = await client.patch(
                "/api/v1/github/organizations/nope",
                json={"sync_enabled": False}, headers=admin(),
            )
        assert r.status_code == 404

    async def test_non_admin_rejected(self, client):
        async with client:
            r = await client.get(
                "/api/v1/github/organizations", headers={"Authorization": "Bearer user-token"}
            )
        assert r.status_code == 403
