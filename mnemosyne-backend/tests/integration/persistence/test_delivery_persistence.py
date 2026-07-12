"""Integration tests for Phase 5.1 adapters (real Postgres)."""

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest

from app.domain.entities.metrics_snapshot import MetricsSnapshot
from app.domain.entities.milestone import Milestone
from app.domain.entities.readiness_snapshot import ReadinessSnapshot
from app.infrastructure.persistence.repositories.misc import (
    PostgresMetricsHistoryRepository,
    PostgresMilestoneRepository,
    PostgresReadinessHistoryRepository,
)
from tests.integration.persistence.test_repositories import seed_repo

NOW = datetime(2026, 7, 7, 12, 0, tzinfo=UTC)

pytestmark = pytest.mark.integration


def _snap(repo_id, day, **kw):
    base = dict(
        repository_id=repo_id, captured_on=date(2026, 7, day), captured_at=NOW,
        open_issues=10, closed_issues=5, open_prs=1, merged_prs=2,
        median_cycle_seconds=3600.0, health_overall=88.0,
    )
    base.update(kw)
    return MetricsSnapshot(**base)


class TestMetricsHistoryRepository:
    async def test_append_and_window(self, session_factory):
        repo = await seed_repo(session_factory)
        adapter = PostgresMetricsHistoryRepository(session_factory)
        await adapter.record(_snap(repo.id, 1, open_issues=20))
        await adapter.record(_snap(repo.id, 2, open_issues=15))
        window = await adapter.list_window(repo.id)
        assert [s.open_issues for s in window] == [20, 15]
        assert window[0].captured_on < window[1].captured_on

    async def test_same_day_upserts_not_duplicates(self, session_factory):
        repo = await seed_repo(session_factory)
        adapter = PostgresMetricsHistoryRepository(session_factory)
        await adapter.record(_snap(repo.id, 3, open_issues=30))
        await adapter.record(_snap(repo.id, 3, open_issues=25))  # same day
        window = await adapter.list_window(repo.id)
        assert len(window) == 1
        assert window[0].open_issues == 25

    async def test_list_all_windows_groups_by_repo(self, session_factory):
        repo = await seed_repo(session_factory)
        adapter = PostgresMetricsHistoryRepository(session_factory)
        await adapter.record(_snap(repo.id, 1, open_issues=20))
        await adapter.record(_snap(repo.id, 2, open_issues=10))
        grouped = await adapter.list_all_windows()
        assert [s.open_issues for s in grouped[repo.id]] == [20, 10]  # chronological

    async def test_prune_deletes_old_keeps_recent(self, session_factory):
        repo = await seed_repo(session_factory)
        adapter = PostgresMetricsHistoryRepository(session_factory)
        today = datetime.now(UTC).date()
        old = today - timedelta(days=400)
        await adapter.record(_snap(repo.id, 1, captured_on=old, open_issues=99))
        await adapter.record(_snap(repo.id, 1, captured_on=today, open_issues=11))
        removed = await adapter.prune(retention_days=365)
        assert removed == 1
        remaining = await adapter.list_window(repo.id)
        assert [s.open_issues for s in remaining] == [11]

    async def test_prune_disabled_is_noop(self, session_factory):
        repo = await seed_repo(session_factory)
        adapter = PostgresMetricsHistoryRepository(session_factory)
        old = datetime.now(UTC).date() - timedelta(days=400)
        await adapter.record(_snap(repo.id, 1, captured_on=old))
        assert await adapter.prune(retention_days=0) == 0
        assert len(await adapter.list_window(repo.id)) == 1


class TestReadinessHistoryRepository:
    def _readiness(self, repo_id, captured_on, gate="READY"):
        return ReadinessSnapshot(
            repository_id=repo_id, captured_on=captured_on, captured_at=NOW, gate=gate
        )

    async def test_prune_deletes_old_keeps_recent(self, session_factory):
        repo = await seed_repo(session_factory)
        adapter = PostgresReadinessHistoryRepository(session_factory)
        today = datetime.now(UTC).date()
        old = today - timedelta(days=400)
        await adapter.record(self._readiness(repo.id, old, gate="MVP"))
        await adapter.record(self._readiness(repo.id, today, gate="DONE"))
        removed = await adapter.prune(retention_days=365)
        assert removed == 1
        remaining = await adapter.list_for_repository(repo.id)
        assert [s.gate for s in remaining] == ["DONE"]

    async def test_prune_disabled_is_noop(self, session_factory):
        repo = await seed_repo(session_factory)
        adapter = PostgresReadinessHistoryRepository(session_factory)
        old = datetime.now(UTC).date() - timedelta(days=400)
        await adapter.record(self._readiness(repo.id, old))
        assert await adapter.prune(retention_days=0) == 0
        assert len(await adapter.list_for_repository(repo.id)) == 1


class TestMilestoneRepository:
    async def test_replace_reconciles(self, session_factory):
        repo = await seed_repo(session_factory)
        adapter = PostgresMilestoneRepository(session_factory)
        await adapter.replace_for_repository(
            repo.id,
            [
                Milestone(id=uuid4(), repository_id=repo.id, number=1, title="v1",
                          state="open", due_on=NOW + timedelta(days=7),
                          open_issues=3, closed_issues=1),
                Milestone(id=uuid4(), repository_id=repo.id, number=2, title="v2",
                          state="open", due_on=None, open_issues=5, closed_issues=0),
            ],
        )
        first = await adapter.list_by_repository(repo.id)
        assert {m.number for m in first} == {1, 2}
        assert next(m for m in first if m.number == 1).percent_complete == 25.0

        # re-sync: v1 updated, v2 removed, v3 added
        await adapter.replace_for_repository(
            repo.id,
            [
                Milestone(id=uuid4(), repository_id=repo.id, number=1, title="v1",
                          state="closed", due_on=None, open_issues=0, closed_issues=4),
                Milestone(id=uuid4(), repository_id=repo.id, number=3, title="v3",
                          state="open", due_on=None, open_issues=2, closed_issues=0),
            ],
        )
        second = await adapter.list_by_repository(repo.id)
        assert {m.number for m in second} == {1, 3}
        assert next(m for m in second if m.number == 1).state == "closed"

    async def test_list_all_groups_by_repo(self, session_factory):
        repo = await seed_repo(session_factory)
        adapter = PostgresMilestoneRepository(session_factory)
        await adapter.replace_for_repository(
            repo.id,
            [
                Milestone(id=uuid4(), repository_id=repo.id, number=1, title="v1",
                          state="open", due_on=None, open_issues=1, closed_issues=0),
            ],
        )
        grouped = await adapter.list_all()
        assert repo.id in grouped
        assert grouped[repo.id][0].number == 1
