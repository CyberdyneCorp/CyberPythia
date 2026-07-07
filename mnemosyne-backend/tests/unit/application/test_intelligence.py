from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.application.errors import UnknownResourceError
from app.application.use_cases.intelligence import IntelligenceService
from app.domain.entities.repository import Repository
from app.domain.entities.source_file import SourceFile
from app.domain.services.repository_health import RepositoryHealthService
from app.domain.services.repository_signals import RepositorySignalsService
from app.domain.value_objects.enums import IndexingMode, RepositoryVisibility
from app.domain.value_objects.full_name import RepositoryFullName
from tests.unit.application.fakes import FakeFilePort, FakeRepositoryPort

NOW = datetime(2026, 7, 7, tzinfo=UTC)


class FakeMetrics:
    def __init__(self) -> None:
        self.rows: dict = {}

    async def get(self, repository_id):
        return self.rows.get(repository_id)

    async def list_all(self):
        return dict(self.rows)


def make_repo(**kw) -> Repository:
    defaults = dict(
        id=uuid4(), connection_id=uuid4(), github_id=1,
        full_name=RepositoryFullName("cyberdyne/skynet"), description="d",
        visibility=RepositoryVisibility.PRIVATE, default_branch="main",
        primary_language="Python", archived=False, github_updated_at=NOW,
        enabled=True, indexing_mode=IndexingMode.CODE_METADATA, last_synced_at=NOW,
    )
    defaults.update(kw)
    return Repository(**defaults)  # type: ignore[arg-type]


def metrics_row(**over) -> dict:
    im = {
        "open_count": 5, "closed_count": 20, "median_resolution_seconds": 2 * 86400.0,
        "stale_issues": [], "by_label": {"bug": 3, "feature": 2}, "by_assignee": {},
    }
    pm = {
        "merged_count": 12, "open_count": 3, "median_time_to_merge_seconds": 86400.0,
        "merge_rate": 0.9, "size_distribution": {"S": 8, "M": 4},
        "stale_prs": [], "by_reviewer": {"alice": 8, "bob": 2},
    }
    summary = {"has_readme": True, "has_docs": True, "has_openspec": True,
               "documents": 4, "openspec_changes": 1}
    im.update(over.get("issue_metrics", {}))
    pm.update(over.get("pr_metrics", {}))
    summary.update(over.get("summary", {}))
    return {"issue_metrics": im, "pr_metrics": pm, "summary": summary,
            "computed_at": NOW.isoformat()}


@pytest.fixture
def env():
    repos = FakeRepositoryPort()
    files = FakeFilePort()
    metrics = FakeMetrics()
    svc = IntelligenceService(
        repos, files, metrics, RepositorySignalsService(), RepositoryHealthService()
    )
    return svc, repos, files, metrics


async def _seed(repos, files, metrics, repo, row=None, paths=()):
    await repos.save(repo)
    if row is not None:
        metrics.rows[repo.id] = row
    if paths:
        files.trees[repo.id] = [
            SourceFile(id=uuid4(), repository_id=repo.id, path=p, extension="", language=None,
                       size_bytes=1, sha="s")
            for p in paths
        ]


async def test_health_scores_synced_repo(env) -> None:
    svc, repos, files, metrics = env
    repo = make_repo()
    await _seed(repos, files, metrics, repo, metrics_row(),
               paths=[".github/workflows/ci.yml", "tests/test_x.py"])
    health = await svc.health(repo.id, NOW)
    assert health.has_data is True
    assert health.grade is not None
    testing = next(c for c in health.components if c.name == "testing_ci")
    assert testing.score == 100.0  # ci + tests present


async def test_health_unknown_repo_raises(env) -> None:
    svc, *_ = env
    with pytest.raises(UnknownResourceError):
        await svc.health(uuid4(), NOW)


async def test_delivery_absent_when_no_metrics(env) -> None:
    svc, repos, files, metrics = env
    repo = make_repo(last_synced_at=None)
    await _seed(repos, files, metrics, repo)
    d = await svc.delivery(repo.id)
    assert d.has_data is False and d.merge_rate is None


async def test_backlog_ratio_and_stale(env) -> None:
    svc, repos, files, metrics = env
    repo = make_repo()
    row = metrics_row(issue_metrics={
        "open_count": 10, "closed_count": 5,
        "stale_issues": [{"number": 1, "title": "old", "age_days": 90.0}],
    })
    await _seed(repos, files, metrics, repo, row)
    b = await svc.backlog(repo.id)
    assert b.open_to_closed_ratio == 2.0
    assert b.stale_issue_count == 1
    assert b.oldest_open_age_days == 90.0


async def test_review_bottleneck_concentration(env) -> None:
    svc, repos, files, metrics = env
    repo = make_repo()
    await _seed(repos, files, metrics, repo, metrics_row())
    r = await svc.review_bottlenecks(repo.id)
    assert r.reviewer_load_concentration == 0.8


async def test_maintenance_risk_flags_reasons(env) -> None:
    svc, repos, files, metrics = env
    repo = make_repo(archived=True, enabled=True, last_synced_at=NOW - timedelta(days=30))
    row = metrics_row(
        issue_metrics={"stale_issues": [{"number": i, "title": "t", "age_days": 40.0}
                                        for i in range(6)]},
    )
    await _seed(repos, files, metrics, repo, row, paths=["README.md"])  # no ci/tests
    risk = await svc.maintenance_risk(repo.id, NOW)
    assert risk.level == "high"
    assert any("archived" in r for r in risk.reasons)
    assert any("CI" in r for r in risk.reasons)


async def test_maintenance_unknown_signals_do_not_inflate(env) -> None:
    svc, repos, files, metrics = env
    # docs_only mode -> no tree -> ci/tests unknown, must not add reasons
    repo = make_repo(indexing_mode=IndexingMode.PROJECT_INTELLIGENCE)
    await _seed(repos, files, metrics, repo, metrics_row())
    risk = await svc.maintenance_risk(repo.id, NOW)
    assert not any("CI" in r or "tests" in r for r in risk.reasons)


async def test_portfolio_overview(env) -> None:
    svc, repos, files, metrics = env
    healthy = make_repo(full_name=RepositoryFullName("cyberdyne/alpha"))
    abandoned = make_repo(
        full_name=RepositoryFullName("cyberdyne/beta"),
        github_updated_at=NOW - timedelta(days=300),
        last_synced_at=NOW - timedelta(days=300),
    )
    never = make_repo(full_name=RepositoryFullName("cyberdyne/gamma"), last_synced_at=None)
    await _seed(repos, files, metrics, healthy, metrics_row())
    await _seed(repos, files, metrics, abandoned, metrics_row())
    await _seed(repos, files, metrics, never)  # no metrics row
    p = await svc.portfolio(NOW)
    assert p.total_repositories == 3
    assert p.scored == 2
    assert "cyberdyne/beta" in p.abandoned
    assert "cyberdyne/alpha" in p.bug_heavy  # has bug labels + active
    # never-synced repo present but marked
    gamma = next(e for e in p.leaderboard if e.full_name == "cyberdyne/gamma")
    assert gamma.has_data is False and gamma.overall is None


async def test_compare_and_onboarding(env) -> None:
    svc, repos, files, metrics = env
    a = make_repo(full_name=RepositoryFullName("cyberdyne/alpha"))
    b = make_repo(full_name=RepositoryFullName("cyberdyne/beta"))
    await _seed(repos, files, metrics, a, metrics_row())
    await _seed(repos, files, metrics, b, metrics_row())
    rows = await svc.compare([a.id, b.id], NOW)
    assert len(rows) == 2 and all(r["grade"] for r in rows)
    onboarding = await svc.onboarding_summary(a.id)
    assert onboarding["full_name"] == "cyberdyne/alpha"
    assert onboarding["has_readme"] is True
