"""Engineering-intelligence application service (spec: engineering-intelligence).

A read/compute layer over persisted ``repository_metrics`` + the captured file
tree. No new GitHub calls. Honours absent-not-zero: every result carries a
``has_data`` flag rather than fabricating zeros.
"""

from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

from app.application.dto.intelligence import (
    BacklogMetrics,
    DeliveryMetrics,
    MaintenanceRisk,
    PortfolioEntry,
    PortfolioOverview,
    ReviewBottlenecks,
    StaleItem,
)
from app.application.errors import UnknownResourceError
from app.domain.entities.repository import Repository
from app.domain.ports.persistence_ports import FilePort, RepositoryPort
from app.domain.services.intelligence_rules import (
    bug_label_count,
    is_abandoned,
    is_active,
    reviewer_load_concentration,
    risk_level,
)
from app.domain.services.repository_health import RepositoryHealthService
from app.domain.services.repository_signals import RepositorySignalsService
from app.domain.value_objects.enums import IndexingMode
from app.domain.value_objects.health import (
    HealthInputs,
    RepositoryHealth,
    RepositorySignals,
)

_STALE_SYNC_DAYS = 14
_HIGH_BACKLOG = 40


class MetricsReader(Protocol):
    async def get(self, repository_id: UUID) -> dict[str, Any] | None: ...
    async def list_all(self) -> dict[UUID, dict[str, Any]]: ...


def _stale_items(raw: list[dict[str, Any]]) -> list[StaleItem]:
    return [
        StaleItem(number=int(i["number"]), title=str(i["title"]), age_days=float(i["age_days"]))
        for i in raw
    ]


def _last_activity(repo: Repository) -> datetime | None:
    return repo.github_updated_at or repo.last_synced_at


class IntelligenceService:
    def __init__(
        self,
        repositories: RepositoryPort,
        files: FilePort,
        metrics: MetricsReader,
        signals: RepositorySignalsService,
        health: RepositoryHealthService,
    ) -> None:
        self._repositories = repositories
        self._files = files
        self._metrics = metrics
        self._signals = signals
        self._health = health

    async def _repo(self, repository_id: UUID) -> Repository:
        repo = await self._repositories.get(repository_id)
        if repo is None:
            raise UnknownResourceError(f"repository {repository_id} not found")
        return repo

    async def _detect_signals(self, repo: Repository) -> RepositorySignals:
        if not repo.indexing_mode.includes_file_tree:
            return RepositorySignals()
        paths = [f.path for f in await self._files.list_by_repository(repo.id)]
        return self._signals.detect(paths, repo.indexing_mode)

    def _inputs(
        self, repo: Repository, metrics: dict[str, Any] | None, signals: RepositorySignals
    ) -> HealthInputs:
        summary = (metrics or {}).get("summary", {})
        im = (metrics or {}).get("issue_metrics", {})
        pm = (metrics or {}).get("pr_metrics", {})
        return HealthInputs(
            synced=metrics is not None and repo.last_synced_at is not None,
            has_readme=bool(summary.get("has_readme")),
            has_docs=bool(summary.get("has_docs")),
            has_openspec=bool(summary.get("has_openspec")),
            merged_prs=int(pm.get("merged_count", 0)),
            median_merge_seconds=pm.get("median_time_to_merge_seconds"),
            merge_rate=pm.get("merge_rate"),
            median_issue_resolution_seconds=im.get("median_resolution_seconds"),
            open_issues=int(im.get("open_count", 0)),
            stale_issue_count=len(im.get("stale_issues", [])),
            open_prs=int(pm.get("open_count", 0)),
            stale_pr_count=len(pm.get("stale_prs", [])),
            last_activity=_last_activity(repo),
            signals=signals,
        )

    async def health(self, repository_id: UUID, now: datetime | None = None) -> RepositoryHealth:
        repo = await self._repo(repository_id)
        metrics = await self._metrics.get(repository_id)
        signals = await self._detect_signals(repo)
        inputs = self._inputs(repo, metrics, signals)
        return self._health.score(inputs, now or datetime.now(UTC))

    async def delivery(self, repository_id: UUID) -> DeliveryMetrics:
        await self._repo(repository_id)
        metrics = await self._metrics.get(repository_id)
        if metrics is None:
            return DeliveryMetrics(False, 0, 0, None, None, None)
        pm = metrics["pr_metrics"]
        im = metrics["issue_metrics"]
        return DeliveryMetrics(
            has_data=True,
            merged_prs=int(pm.get("merged_count", 0)),
            closed_issues=int(im.get("closed_count", 0)),
            merge_rate=pm.get("merge_rate"),
            median_merge_seconds=pm.get("median_time_to_merge_seconds"),
            median_issue_resolution_seconds=im.get("median_resolution_seconds"),
            pr_size_distribution=dict(pm.get("size_distribution", {})),
        )

    async def backlog(self, repository_id: UUID) -> BacklogMetrics:
        await self._repo(repository_id)
        metrics = await self._metrics.get(repository_id)
        if metrics is None:
            return BacklogMetrics(False, 0, 0, None, 0, None)
        im = metrics["issue_metrics"]
        stale = _stale_items(im.get("stale_issues", []))
        open_count = int(im.get("open_count", 0))
        closed_count = int(im.get("closed_count", 0))
        return BacklogMetrics(
            has_data=True,
            open_issues=open_count,
            closed_issues=closed_count,
            open_to_closed_ratio=(open_count / closed_count) if closed_count else None,
            stale_issue_count=len(stale),
            oldest_open_age_days=max((s.age_days for s in stale), default=None),
            stale_issues=stale,
        )

    async def review_bottlenecks(self, repository_id: UUID) -> ReviewBottlenecks:
        await self._repo(repository_id)
        metrics = await self._metrics.get(repository_id)
        if metrics is None:
            return ReviewBottlenecks(False, 0, None)
        pm = metrics["pr_metrics"]
        by_reviewer = dict(pm.get("by_reviewer", {}))
        stale = _stale_items(pm.get("stale_prs", []))
        return ReviewBottlenecks(
            has_data=True,
            stale_pr_count=len(stale),
            reviewer_load_concentration=reviewer_load_concentration(by_reviewer),
            stale_prs=stale,
            by_reviewer=by_reviewer,
        )

    async def maintenance_risk(
        self, repository_id: UUID, now: datetime | None = None
    ) -> MaintenanceRisk:
        repo = await self._repo(repository_id)
        metrics = await self._metrics.get(repository_id)
        if metrics is None:
            return MaintenanceRisk(False, "low", ["not synced"])
        now = now or datetime.now(UTC)
        signals = await self._detect_signals(repo)
        im, pm = metrics["issue_metrics"], metrics["pr_metrics"]
        reasons: list[str] = []
        if repo.archived and repo.enabled:
            reasons.append("archived but still enabled")
        if signals.has_ci is False:
            reasons.append("no CI configured")
        if signals.has_tests is False:
            reasons.append("no tests detected")
        stale = len(im.get("stale_issues", [])) + len(pm.get("stale_prs", []))
        if stale >= 5:
            reasons.append(f"{stale} stale open items")
        if repo.last_synced_at and (now - repo.last_synced_at).days >= _STALE_SYNC_DAYS:
            reasons.append("stale last sync")
        if int(im.get("open_count", 0)) >= _HIGH_BACKLOG:
            reasons.append("high open-issue backlog")
        return MaintenanceRisk(True, risk_level(len(reasons)).value, reasons)

    async def portfolio(self, now: datetime | None = None) -> PortfolioOverview:
        now = now or datetime.now(UTC)
        repos = await self._repositories.list_all(enabled_only=True)
        all_metrics = await self._metrics.list_all()
        entries: list[PortfolioEntry] = []
        active: list[tuple[str, int]] = []
        abandoned: list[str] = []
        bugs: list[tuple[str, int]] = []
        for repo in repos:
            metrics = all_metrics.get(repo.id)
            signals = RepositorySignals()  # portfolio scoring skips per-repo tree reads
            health = self._health.score(self._inputs(repo, metrics, signals), now)
            entries.append(
                PortfolioEntry(
                    repository_id=str(repo.id),
                    full_name=str(repo.full_name),
                    has_data=health.has_data,
                    overall=health.overall,
                    grade=health.grade.value if health.grade else None,
                )
            )
            last = _last_activity(repo)
            if is_abandoned(last, now):
                abandoned.append(str(repo.full_name))
            if metrics is not None:
                im, pm = metrics["issue_metrics"], metrics["pr_metrics"]
                if is_active(last, now):
                    volume = int(pm.get("merged_count", 0)) + int(im.get("closed_count", 0))
                    active.append((str(repo.full_name), volume))
                bug_n = bug_label_count(dict(im.get("by_label", {})))
                if bug_n:
                    bugs.append((str(repo.full_name), bug_n))
        entries.sort(key=lambda e: (e.overall is None, -(e.overall or 0)))
        active.sort(key=lambda kv: -kv[1])
        bugs.sort(key=lambda kv: -kv[1])
        return PortfolioOverview(
            total_repositories=len(repos),
            scored=sum(1 for e in entries if e.has_data),
            leaderboard=entries,
            most_active=[name for name, _ in active[:10]],
            abandoned=sorted(abandoned),
            bug_heavy=[name for name, _ in bugs[:10]],
        )

    async def compare(
        self, repository_ids: list[UUID], now: datetime | None = None
    ) -> list[dict[str, Any]]:
        now = now or datetime.now(UTC)
        out: list[dict[str, Any]] = []
        for rid in repository_ids:
            health = await self.health(rid, now)
            delivery = await self.delivery(rid)
            repo = await self._repo(rid)
            out.append(
                {
                    "repository_id": str(rid),
                    "full_name": str(repo.full_name),
                    "overall": health.overall,
                    "grade": health.grade.value if health.grade else None,
                    "merge_rate": delivery.merge_rate,
                    "median_merge_seconds": delivery.median_merge_seconds,
                    "open_issues": delivery.closed_issues,
                }
            )
        return out

    async def onboarding_summary(self, repository_id: UUID) -> dict[str, Any]:
        repo = await self._repo(repository_id)
        health = await self.health(repository_id)
        metrics = await self._metrics.get(repository_id)
        summary = (metrics or {}).get("summary", {})
        return {
            "full_name": str(repo.full_name),
            "description": repo.description,
            "primary_language": repo.primary_language,
            "indexing_mode": repo.indexing_mode.value
            if isinstance(repo.indexing_mode, IndexingMode)
            else str(repo.indexing_mode),
            "health_grade": health.grade.value if health.grade else None,
            "health_overall": health.overall,
            "has_readme": bool(summary.get("has_readme")),
            "has_docs": bool(summary.get("has_docs")),
            "has_openspec": bool(summary.get("has_openspec")),
            "documents": int(summary.get("documents", 0)),
            "openspec_changes": int(summary.get("openspec_changes", 0)),
            "top_findings": [
                {"severity": f.severity.value, "message": f.message}
                for f in health.findings[:5]
            ],
        }
