"""PM/PO delivery-intelligence application service (spec: delivery-intelligence).

Composes the pure delivery statistics over persisted issues/PRs/milestones and the
metrics time-series. Absent-not-zero: every result carries ``has_data`` / reasons
instead of fabricating zeros.
"""

from datetime import UTC, datetime, timedelta
from itertools import pairwise
from typing import Any
from uuid import UUID

from app.application.dto.delivery import (
    BacklogForecast,
    DeliveryScorecardEntry,
    FlowMetrics,
    MilestoneProgress,
    PercentileBlock,
    QualitySignals,
    TeamLoad,
    ThroughputTrend,
    TrendPoint,
    WorkMix,
)
from app.application.errors import UnknownResourceError
from app.application.use_cases.intelligence import MetricsReader
from app.domain.entities.issue import Issue
from app.domain.entities.metrics_snapshot import MetricsSnapshot
from app.domain.entities.milestone import Milestone
from app.domain.entities.pull_request import PullRequest
from app.domain.entities.repository import Repository
from app.domain.ports.persistence_ports import (
    IssuePort,
    MetricsHistoryPort,
    MilestonePort,
    PullRequestPort,
    RepositoryPort,
)
from app.domain.services import delivery_stats as ds
from app.domain.value_objects.enums import IssueState, PullRequestState

_DAY = 86400.0
_MIN_TREND_POINTS = 2


def _pct(values: list[float]) -> PercentileBlock:
    p = ds.percentiles(values)
    return PercentileBlock(n=p.n, p50=p.p50, p85=p.p85, p95=p.p95)


def _open_issue(i: Issue) -> bool:
    return i.state is IssueState.OPEN


def _open_pr(p: PullRequest) -> bool:
    return p.state is PullRequestState.OPEN


class DeliveryIntelligenceService:
    def __init__(
        self,
        repositories: RepositoryPort,
        issues: IssuePort,
        pull_requests: PullRequestPort,
        milestones: MilestonePort,
        history: MetricsHistoryPort,
        metrics: "MetricsReader",
    ) -> None:
        self._repositories = repositories
        self._issues = issues
        self._pull_requests = pull_requests
        self._milestones = milestones
        self._history = history
        self._metrics = metrics

    async def _repo(self, repository_id: UUID) -> Repository:
        repo = await self._repositories.get(repository_id)
        if repo is None or not repo.enabled:
            # A disabled repository is no longer indexed — don't surface stale metrics.
            raise UnknownResourceError(f"repository {repository_id} is not indexed")
        return repo

    async def flow(self, repository_id: UUID, now: datetime | None = None) -> FlowMetrics:
        await self._repo(repository_id)
        now = now or datetime.now(UTC)
        issues = await self._issues.list_by_repository(repository_id)
        prs = await self._pull_requests.list_by_repository(repository_id)
        if not issues and not prs:
            return FlowMetrics(False, _pct([]), _pct([]), 0, 0)
        resolution = [t for i in issues if (t := i.resolution_time_seconds) is not None]
        merges = [t for p in prs if (t := p.time_to_merge_seconds) is not None]
        open_issues = [i for i in issues if _open_issue(i)]
        open_prs = [p for p in prs if _open_pr(p)]
        issue_ages = [a for i in open_issues if (a := i.age_seconds(now)) is not None]
        pr_ages = [
            (now - p.created_at).total_seconds() for p in open_prs if p.created_at is not None
        ]
        untriaged = sum(1 for i in open_issues if not i.labels or not i.assignees)
        return FlowMetrics(
            has_data=True,
            resolution_seconds=_pct(resolution),
            merge_seconds=_pct(merges),
            wip_issues=len(open_issues),
            wip_prs=len(open_prs),
            issue_aging=ds.aging_buckets(issue_ages),
            pr_aging=ds.aging_buckets(pr_ages),
            untriaged_issues=untriaged,
        )

    async def _series(self, repository_id: UUID) -> list[MetricsSnapshot]:
        return await self._history.list_window(repository_id, days=180)

    @staticmethod
    def _trend_points(series: list[MetricsSnapshot]) -> list[TrendPoint]:
        points: list[TrendPoint] = []
        for prev, cur in pairwise(series):
            closed = max(0, cur.closed_issues - prev.closed_issues)
            net = cur.open_issues - prev.open_issues
            points.append(
                TrendPoint(
                    date=cur.captured_on.isoformat(),
                    closed_issues=closed,
                    open_issues=cur.open_issues,
                    net_flow=net,
                )
            )
        return points

    async def throughput(self, repository_id: UUID) -> ThroughputTrend:
        await self._repo(repository_id)
        series = await self._series(repository_id)
        if len(series) < _MIN_TREND_POINTS:
            return ThroughputTrend(False, reason="insufficient history")
        return ThroughputTrend(True, points=self._trend_points(series))

    async def forecast(
        self, repository_id: UUID, now: datetime | None = None
    ) -> BacklogForecast:
        await self._repo(repository_id)
        now = now or datetime.now(UTC)
        series = await self._series(repository_id)
        if len(series) < _MIN_TREND_POINTS:
            return BacklogForecast(False, 0, None, None, None, "insufficient history")
        open_count = series[-1].open_issues
        closed_deltas = [p.closed_issues for p in self._trend_points(series)]
        f = ds.backlog_forecast(open_count, closed_deltas, min_points=1)
        date = None
        if f.projected_days is not None:
            date = (now + timedelta(days=f.projected_days)).date().isoformat()
        return BacklogForecast(
            has_data=True,
            open_issues=open_count,
            close_rate_per_day=f.close_rate_per_day,
            projected_days_to_clear=f.projected_days,
            projected_clear_date=date,
            reason=f.reason,
        )

    async def work_mix(self, repository_id: UUID) -> WorkMix:
        await self._repo(repository_id)
        issues = await self._issues.list_by_repository(repository_id)
        if not issues:
            return WorkMix(False)
        dist = ds.work_mix([i.labels for i in issues])
        total = sum(dist.values())
        bug_ratio = dist["bug"] / total if total else None
        return WorkMix(True, distribution=dist, bug_ratio=bug_ratio)

    async def quality(self, repository_id: UUID) -> QualitySignals:
        await self._repo(repository_id)
        issues = await self._issues.list_by_repository(repository_id)
        if not issues:
            return QualitySignals(False, None, None, None)
        dist = ds.work_mix([i.labels for i in issues])
        total = len(issues)
        bug_ratio = dist["bug"] / total if total else None
        reopened = sum(1 for i in issues if i.reopened_count > 0)
        reopened_rate = reopened / total if total else None
        fr = [t for i in issues if (t := i.first_response_seconds) is not None]
        first_response = _pct(fr) if fr else None
        return QualitySignals(True, bug_ratio, reopened_rate, first_response)

    async def milestones(
        self, repository_id: UUID, now: datetime | None = None
    ) -> list[MilestoneProgress]:
        await self._repo(repository_id)
        now = now or datetime.now(UTC)
        milestones = await self._milestones.list_by_repository(repository_id)
        series = await self._series(repository_id)
        rate = self._close_rate_per_day(series)
        out: list[MilestoneProgress] = []
        for m in milestones:
            projected, at_risk = self._project_milestone(m.open_issues, m.due_on, rate, now)
            out.append(
                MilestoneProgress(
                    number=m.number,
                    title=m.title,
                    state=m.state,
                    percent_complete=m.percent_complete,
                    open_issues=m.open_issues,
                    closed_issues=m.closed_issues,
                    due_on=m.due_on.date().isoformat() if m.due_on else None,
                    projected_completion=projected,
                    at_risk=at_risk,
                )
            )
        return out

    @staticmethod
    def _close_rate_per_day(series: list[MetricsSnapshot]) -> float | None:
        if len(series) < _MIN_TREND_POINTS:
            return None
        closed = [
            max(0, cur.closed_issues - prev.closed_issues)
            for prev, cur in pairwise(series)
        ]
        rate = sum(closed) / len(closed)
        return rate if rate > 0 else None

    @staticmethod
    def _project_milestone(
        open_issues: int, due_on: datetime | None, rate: float | None, now: datetime
    ) -> tuple[str | None, bool]:
        if open_issues == 0:
            return now.date().isoformat(), False
        if rate is None or rate <= 0:
            return None, False
        projected = now + timedelta(days=open_issues / rate)
        at_risk = due_on is not None and projected > due_on
        return projected.date().isoformat(), at_risk

    async def team_load(self, repository_id: UUID) -> TeamLoad:
        await self._repo(repository_id)
        issues = await self._issues.list_by_repository(repository_id)
        prs = await self._pull_requests.list_by_repository(repository_id)
        if not issues and not prs:
            return TeamLoad(False)
        open_by_assignee: dict[str, int] = {}
        for i in issues:
            if _open_issue(i):
                for a in i.assignees:
                    open_by_assignee[a] = open_by_assignee.get(a, 0) + 1
        reviews: dict[str, int] = {}
        by_author: dict[str, int] = {}
        for p in prs:
            for r in p.reviewers:
                reviews[r] = reviews.get(r, 0) + 1
            if p.author:
                by_author[p.author] = by_author.get(p.author, 0) + 1
        return TeamLoad(
            has_data=True,
            open_by_assignee=dict(sorted(open_by_assignee.items(), key=lambda kv: -kv[1])),
            reviews_by_reviewer=dict(sorted(reviews.items(), key=lambda kv: -kv[1])),
            bus_factor=ds.bus_factor(by_author),
        )

    async def delivery_scorecard(
        self, now: datetime | None = None
    ) -> list[DeliveryScorecardEntry]:
        """Portfolio roll-up computed from batched reads (no per-repo query loop).

        Reads the enabled repos, all persisted metrics rows, all snapshot series,
        and all milestones in four queries, then shapes each entry in memory — so
        the scorecard scales to hundreds of repos.
        """
        now = now or datetime.now(UTC)
        repos = await self._repositories.list_all(enabled_only=True)
        all_metrics = await self._metrics.list_all()
        all_history = await self._history.list_all_windows(days=180)
        all_milestones = await self._milestones.list_all()
        return [
            self._scorecard_entry(
                repo,
                all_metrics.get(repo.id),
                all_history.get(repo.id, []),
                all_milestones.get(repo.id, []),
                now,
            )
            for repo in repos
        ]

    def _scorecard_entry(
        self,
        repo: Repository,
        metrics: dict[str, Any] | None,
        series: list[MetricsSnapshot],
        milestones: list[Milestone],
        now: datetime,
    ) -> DeliveryScorecardEntry:
        median = (metrics or {}).get("issue_metrics", {}).get("median_resolution_seconds")
        rate = self._close_rate_per_day(series)
        backlog: bool | None = None
        if len(series) >= _MIN_TREND_POINTS:
            closed = [p.closed_issues for p in self._trend_points(series)]
            backlog = ds.backlog_forecast(
                series[-1].open_issues, closed, min_points=1
            ).projected_days is not None
        at_risk = sum(
            1
            for m in milestones
            if self._project_milestone(m.open_issues, m.due_on, rate, now)[1]
        )
        return DeliveryScorecardEntry(
            repository_id=str(repo.id),
            full_name=str(repo.full_name),
            has_data=metrics is not None,
            median_cycle_days=round(median / _DAY, 1) if median is not None else None,
            throughput_direction=self._direction(series),
            backlog_shrinking=backlog,
            at_risk_milestones=at_risk,
        )

    @staticmethod
    def _direction(series: list[MetricsSnapshot]) -> str | None:
        if len(series) < _MIN_TREND_POINTS:
            return None
        first, last = series[0].open_issues, series[-1].open_issues
        if last < first:
            return "down"
        if last > first:
            return "up"
        return "flat"
