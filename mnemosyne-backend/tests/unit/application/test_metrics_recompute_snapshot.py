from datetime import UTC, datetime
from uuid import uuid4

from app.application.metrics_recompute import MetricsRecomputeService
from app.domain.entities.repository import Repository
from app.domain.value_objects.enums import IndexingMode, RepositoryVisibility
from app.domain.value_objects.full_name import RepositoryFullName
from tests.unit.application.fakes import (
    FakeDocumentPort,
    FakeIssuePort,
    FakeOpenSpecPort,
    FakePullRequestPort,
)
from tests.unit.application.test_delivery_intelligence import FakeHistoryPort

NOW = datetime(2026, 7, 7, tzinfo=UTC)


class FakeMetricsStore:
    def __init__(self) -> None:
        self.saved: dict = {}

    async def save(self, repository_id, **kw) -> None:
        self.saved[repository_id] = kw

    async def get(self, repository_id):
        return self.saved.get(repository_id)


def make_repo() -> Repository:
    return Repository(
        id=uuid4(), connection_id=uuid4(), github_id=1,
        full_name=RepositoryFullName("cyberdyne/a"), description="d",
        visibility=RepositoryVisibility.PRIVATE, default_branch="main",
        primary_language="Python", archived=False, github_updated_at=NOW,
        enabled=True, indexing_mode=IndexingMode.PROJECT_INTELLIGENCE, last_synced_at=NOW,
    )


async def test_recompute_writes_metrics_and_appends_snapshot() -> None:
    store, history = FakeMetricsStore(), FakeHistoryPort()
    svc = MetricsRecomputeService(
        FakeIssuePort(), FakePullRequestPort(), FakeDocumentPort(), FakeOpenSpecPort(),
        store, history=history,
    )
    repo = make_repo()
    await svc.recompute(repo)
    # current metrics row still written
    assert repo.id in store.saved
    assert "summary" in store.saved[repo.id]
    # AND a snapshot appended for today
    snaps = history.rows[repo.id]
    assert len(snaps) == 1
    # recompute stamps the real current date (not the fixture NOW) — assert against today
    assert snaps[0].captured_on == datetime.now(UTC).date()
    assert snaps[0].health_overall is not None  # scored portfolio-style


async def test_recompute_without_history_is_noop_for_snapshots() -> None:
    store = FakeMetricsStore()
    svc = MetricsRecomputeService(
        FakeIssuePort(), FakePullRequestPort(), FakeDocumentPort(), FakeOpenSpecPort(), store,
    )
    repo = make_repo()
    await svc.recompute(repo)  # no history wired -> must not raise
    assert repo.id in store.saved


async def test_recompute_preserves_has_releases_when_not_supplied() -> None:
    store = FakeMetricsStore()
    svc = MetricsRecomputeService(
        FakeIssuePort(), FakePullRequestPort(), FakeDocumentPort(), FakeOpenSpecPort(), store,
    )
    repo = make_repo()
    # A full sync captured releases=True...
    await svc.recompute(repo, has_releases=True)
    assert store.saved[repo.id]["summary"]["has_releases"] is True
    await svc.recompute(repo, vulnerabilities={"critical": 2, "high": 1})
    # ...an incremental recompute (no values supplied) must not clobber either signal.
    await svc.recompute(repo)
    assert store.saved[repo.id]["summary"]["has_releases"] is True
    assert store.saved[repo.id]["summary"]["vulnerabilities"] == {"critical": 2, "high": 1}
