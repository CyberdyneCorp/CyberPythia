"""Integration tests for sync-run history + recent sync-job listing (real Postgres)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.domain.entities.sync_job import SyncJob
from app.domain.entities.sync_run import SyncRun
from app.domain.value_objects.enums import IndexingMode, SyncStatus, SyncStep
from app.infrastructure.persistence.repositories.misc import (
    PostgresSyncJobRepository,
    PostgresSyncRunRepository,
)
from tests.integration.persistence.test_repositories import seed_repo

NOW = datetime(2026, 7, 7, 12, 0, tzinfo=UTC)

pytestmark = pytest.mark.integration


def _run(finished, **kw) -> SyncRun:
    base = dict(
        id=uuid4(), trigger="scheduler", started_at=finished - timedelta(minutes=20),
        finished_at=finished, discovered=345, newly_enabled=2, skipped_archived=107,
        enqueued=238, skipped=1, failed=3,
    )
    base.update(kw)
    return SyncRun(**base)  # type: ignore[arg-type]


class TestSyncRunHistory:
    async def test_record_and_list_newest_first(self, session_factory):
        adapter = PostgresSyncRunRepository(session_factory)
        await adapter.record(_run(NOW - timedelta(days=1), enqueued=100))
        await adapter.record(_run(NOW, enqueued=238))
        runs = await adapter.list_recent()
        assert [r.enqueued for r in runs] == [238, 100]  # newest first
        assert runs[0].newly_enabled == 2


class TestSyncJobListRecent:
    async def test_list_recent_across_repos(self, session_factory):
        repo = await seed_repo(session_factory)
        jobs = PostgresSyncJobRepository(session_factory)
        for i in range(3):
            job = SyncJob(
                id=uuid4(), repository_id=repo.id,
                mode=IndexingMode.PROJECT_INTELLIGENCE, triggered_by="scheduler",
            )
            job.plan()
            job.start(NOW + timedelta(minutes=i))
            job.record_step(SyncStep.ISSUES, SyncStatus.FAILED, error="rate limited")
            job.finish(NOW + timedelta(minutes=i))
            await jobs.save(job)
        recent = await jobs.list_recent(limit=2)
        assert len(recent) == 2
        assert recent[0].started_at >= recent[1].started_at  # newest first
        assert recent[0].status is SyncStatus.FAILED
