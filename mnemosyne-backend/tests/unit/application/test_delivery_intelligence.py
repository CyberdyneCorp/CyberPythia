from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.errors import UnknownResourceError
from app.application.use_cases.delivery_intelligence import DeliveryIntelligenceService
from app.domain.entities.issue import Issue
from app.domain.entities.metrics_snapshot import MetricsSnapshot
from app.domain.entities.milestone import Milestone
from app.domain.entities.pull_request import PullRequest
from app.domain.entities.repository import Repository
from app.domain.value_objects.enums import (
    IndexingMode,
    IssueState,
    PullRequestState,
    RepositoryVisibility,
)
from app.domain.value_objects.full_name import RepositoryFullName
from tests.unit.application.fakes import (
    FakeIssuePort,
    FakePullRequestPort,
    FakeRepositoryPort,
)

NOW = datetime(2026, 7, 7, tzinfo=UTC)


class FakeMilestonePort:
    def __init__(self) -> None:
        self.items: dict = {}

    async def replace_for_repository(self, repository_id, milestones) -> None:
        self.items[repository_id] = milestones

    async def list_by_repository(self, repository_id):
        return list(self.items.get(repository_id, []))

    async def list_all(self):
        return {k: list(v) for k, v in self.items.items()}


class FakeHistoryPort:
    def __init__(self) -> None:
        self.rows: dict = {}

    async def record(self, snapshot) -> None:
        self.rows.setdefault(snapshot.repository_id, []).append(snapshot)

    async def list_window(self, repository_id, *, days=180):
        return sorted(self.rows.get(repository_id, []), key=lambda s: s.captured_on)

    async def list_all_windows(self, *, days=180):
        return {
            rid: sorted(snaps, key=lambda s: s.captured_on)
            for rid, snaps in self.rows.items()
        }

    async def prune(self, *, daily_days=180) -> int:
        return 0


class FakeMetricsReader:
    def __init__(self) -> None:
        self.rows: dict = {}

    async def get(self, repository_id):
        return self.rows.get(repository_id)

    async def list_all(self):
        return dict(self.rows)


def make_repo(**kw) -> Repository:
    d = dict(
        id=uuid4(), connection_id=uuid4(), github_id=1,
        full_name=RepositoryFullName("cyberdyne/skynet"), description="d",
        visibility=RepositoryVisibility.PRIVATE, default_branch="main",
        primary_language="Python", archived=False, github_updated_at=NOW,
        enabled=True, indexing_mode=IndexingMode.PROJECT_INTELLIGENCE, last_synced_at=NOW,
    )
    d.update(kw)
    return Repository(**d)  # type: ignore[arg-type]


def issue(number, repo_id, *, state=IssueState.CLOSED, days_open=3.0, labels=None,
          assignees=None, reopened=0, first_response_days=None) -> Issue:
    created = NOW - timedelta(days=days_open)
    closed = NOW if state is IssueState.CLOSED else None
    fr = created + timedelta(days=first_response_days) if first_response_days is not None else None
    return Issue(
        id=uuid4(), repository_id=repo_id, github_issue_id=number, number=number,
        title=f"i{number}", body=None, state=state, author="alice",
        labels=labels or [], assignees=assignees or [], milestone=None,
        created_at=created, updated_at=NOW, closed_at=closed, comments_count=0,
        first_response_at=fr, reopened_count=reopened,
    )


def pr(number, repo_id, *, merged=True, days=2.0, author="alice", reviewers=None) -> PullRequest:
    created = NOW - timedelta(days=days)
    return PullRequest(
        id=uuid4(), repository_id=repo_id, github_pr_id=number, number=number,
        title=f"p{number}", body=None,
        state=PullRequestState.MERGED if merged else PullRequestState.OPEN,
        merged=merged, author=author, reviewers=reviewers or ["bob"],
        created_at=created, updated_at=NOW, closed_at=NOW if merged else None,
        merged_at=NOW if merged else None, first_review_at=None,
    )


def _snap(repo_id, day, closed, opened) -> MetricsSnapshot:
    return MetricsSnapshot(
        repository_id=repo_id, captured_on=date(2026, 7, day),
        captured_at=NOW, open_issues=opened, closed_issues=closed,
        open_prs=0, merged_prs=0, median_cycle_seconds=None, health_overall=80.0,
    )


@pytest.fixture
async def env():
    repos, issues, prs = FakeRepositoryPort(), FakeIssuePort(), FakePullRequestPort()
    milestones, history = FakeMilestonePort(), FakeHistoryPort()
    metrics = FakeMetricsReader()
    svc = DeliveryIntelligenceService(repos, issues, prs, milestones, history, metrics)
    repo = make_repo()
    await repos.save(repo)
    return SimpleNamespace(
        svc=svc, repos=repos, issues=issues, prs=prs,
        milestones=milestones, history=history, metrics=metrics, repo=repo,
    )


async def test_flow_percentiles_and_aging(env) -> None:
    rid = env.repo.id
    for n, d in enumerate([1, 5, 20, 100], start=1):
        await env.issues.save_many([issue(n, rid, state=IssueState.OPEN, days_open=d)])
    for n in range(10, 13):
        await env.issues.save_many([issue(n, rid, state=IssueState.CLOSED, days_open=n - 8)])
    await env.prs.save_many([pr(1, rid)])
    flow = await env.svc.flow(rid, NOW)
    assert flow.has_data
    assert flow.wip_issues == 4
    assert sum(flow.issue_aging.values()) == 4
    assert flow.issue_aging["90+"] == 1
    assert flow.resolution_seconds.n == 3
    assert flow.merge_seconds.n == 1


async def test_flow_untriaged(env) -> None:
    rid = env.repo.id
    await env.issues.save_many([issue(1, rid, state=IssueState.OPEN, labels=[], assignees=[])])
    await env.issues.save_many(
        [issue(2, rid, state=IssueState.OPEN, labels=["bug"], assignees=["x"])]
    )
    flow = await env.svc.flow(rid, NOW)
    assert flow.untriaged_issues == 1


async def test_flow_no_data(env) -> None:
    flow = await env.svc.flow(env.repo.id, NOW)
    assert flow.has_data is False


async def test_unknown_repo_raises(env) -> None:
    with pytest.raises(UnknownResourceError):
        await env.svc.flow(uuid4(), NOW)


async def test_disabled_repo_treated_as_not_indexed(env) -> None:
    disabled = make_repo(enabled=False)
    await env.repos.save(disabled)
    with pytest.raises(UnknownResourceError):
        await env.svc.flow(disabled.id, NOW)


async def test_throughput_and_forecast(env) -> None:
    rid = env.repo.id
    for day, closed, opened in [(1, 5, 20), (2, 10, 15), (3, 16, 9)]:
        await env.history.record(_snap(rid, day, closed, opened))
    tr = await env.svc.throughput(rid)
    assert tr.has_data and len(tr.points) == 2
    assert tr.points[0].closed_issues == 5 and tr.points[0].net_flow == -5
    fc = await env.svc.forecast(rid, NOW)
    assert fc.has_data and fc.projected_days_to_clear is not None
    assert fc.projected_clear_date is not None
    assert fc.reason is None


async def test_throughput_insufficient_history(env) -> None:
    await env.history.record(_snap(env.repo.id, 1, 5, 20))
    tr = await env.svc.throughput(env.repo.id)
    assert tr.has_data is False and tr.reason == "insufficient history"


async def test_forecast_backlog_growing(env) -> None:
    rid = env.repo.id
    for day, closed, opened in [(1, 5, 10), (2, 5, 20)]:  # nothing closed between
        await env.history.record(_snap(rid, day, closed, opened))
    fc = await env.svc.forecast(rid, NOW)
    assert fc.projected_days_to_clear is None and fc.reason == "backlog not shrinking"


async def test_work_mix_and_quality(env) -> None:
    rid = env.repo.id
    await env.issues.save_many([issue(1, rid, labels=["bug"], reopened=1)])
    await env.issues.save_many([issue(2, rid, labels=["feature"])])
    await env.issues.save_many([issue(3, rid, labels=["feature"], first_response_days=0.5)])
    await env.issues.save_many([issue(4, rid, labels=["chore"])])
    wm = await env.svc.work_mix(rid)
    assert wm.distribution == {"feature": 2, "bug": 1, "tech_debt": 1, "docs": 0, "other": 0}
    assert wm.bug_ratio == 0.25
    q = await env.svc.quality(rid)
    assert q.bug_ratio == 0.25
    assert q.reopened_rate == 0.25
    assert q.first_response_seconds is not None and q.first_response_seconds.n == 1


async def test_team_load_and_bus_factor(env) -> None:
    rid = env.repo.id
    await env.issues.save_many([issue(1, rid, state=IssueState.OPEN, assignees=["alice"])])
    await env.issues.save_many(
        [issue(2, rid, state=IssueState.OPEN, assignees=["alice", "bob"])]
    )
    for n in range(1, 9):
        await env.prs.save_many([pr(n, rid, author="alice")])
    await env.prs.save_many([pr(9, rid, author="bob")])
    tl = await env.svc.team_load(rid)
    assert tl.open_by_assignee["alice"] == 2
    assert tl.bus_factor == 1  # alice owns 8/9 PRs


async def test_milestone_progress_and_at_risk(env) -> None:
    rid = env.repo.id
    for day, closed, opened in [(1, 0, 10), (2, 2, 8)]:  # ~2 closed/period
        await env.history.record(_snap(rid, day, closed, opened))
    env.milestones.items[rid] = [
        Milestone(id=uuid4(), repository_id=rid, number=1, title="v1", state="open",
                  due_on=NOW + timedelta(days=1), open_issues=8, closed_issues=2),
    ]
    result = await env.svc.milestones(rid, NOW)
    assert len(result) == 1
    m = result[0]
    assert m.percent_complete == 20.0
    assert m.projected_completion is not None
    assert m.at_risk is True  # 8 open / 2-per-period > 1 day to due


async def test_delivery_scorecard(env) -> None:
    rid = env.repo.id
    # scorecard median now comes from the persisted metrics row (batched), not a live load
    env.metrics.rows[rid] = {
        "issue_metrics": {"median_resolution_seconds": 4 * 86400.0},
        "pr_metrics": {},
        "summary": {},
    }
    for day, closed, opened in [(1, 5, 20), (2, 10, 9)]:
        await env.history.record(_snap(rid, day, closed, opened))
    board = await env.svc.delivery_scorecard(NOW)
    assert len(board) == 1
    entry = board[0]
    assert entry.has_data
    assert entry.throughput_direction == "down"  # open 20 -> 9
    assert entry.median_cycle_days == 4.0


async def test_delivery_scorecard_no_metrics_is_marked(env) -> None:
    # enabled repo with no metrics row -> has_data False, no fabricated numbers
    board = await env.svc.delivery_scorecard(NOW)
    assert len(board) == 1
    assert board[0].has_data is False
    assert board[0].median_cycle_days is None
