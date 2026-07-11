"""Recompute a repository's metrics + summary (design D5).

Shared by the full sync's metrics step and the webhook-driven incremental
single-issue / single-PR syncs, so both compute identically.
"""

from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any, Protocol

from app.domain.entities.metrics_snapshot import MetricsSnapshot
from app.domain.entities.repository import Repository
from app.domain.ports.persistence_ports import (
    DocumentPort,
    IssuePort,
    OpenSpecPort,
    PullRequestPort,
)
from app.domain.services.issue_metrics import IssueMetricsService
from app.domain.services.pr_metrics import PullRequestMetricsService
from app.domain.services.repository_health import RepositoryHealthService
from app.domain.value_objects.enums import DocumentType
from app.domain.value_objects.health import HealthInputs, RepositorySignals


class MetricsWriterProtocol(Protocol):  # PostgresMetricsRepository-compatible
    async def save(
        self,
        repository_id: Any,
        *,
        issue_metrics: dict[str, Any],
        pr_metrics: dict[str, Any],
        summary: dict[str, Any],
        computed_at: datetime,
    ) -> None: ...

    async def get(self, repository_id: Any) -> dict[str, Any] | None: ...


class MetricsHistoryProtocol(Protocol):  # PostgresMetricsHistoryRepository-compatible
    async def record(self, snapshot: MetricsSnapshot) -> None: ...


class MetricsRecomputeService:
    def __init__(
        self,
        issues: IssuePort,
        pull_requests: PullRequestPort,
        documents: DocumentPort,
        openspec: OpenSpecPort,
        metrics_store: MetricsWriterProtocol,
        issue_metrics: IssueMetricsService | None = None,
        pr_metrics: PullRequestMetricsService | None = None,
        history: MetricsHistoryProtocol | None = None,
        health: RepositoryHealthService | None = None,
    ) -> None:
        self._issues = issues
        self._pull_requests = pull_requests
        self._documents = documents
        self._openspec = openspec
        self._metrics_store = metrics_store
        self._issue_metrics = issue_metrics or IssueMetricsService()
        self._pr_metrics = pr_metrics or PullRequestMetricsService()
        self._history = history
        self._health = health or RepositoryHealthService()

    async def recompute(
        self,
        repository: Repository,
        *,
        has_releases: bool | None = None,
        vulnerabilities: dict[str, int] | None = None,
    ) -> None:
        now = datetime.now(UTC)
        # Preserve best-effort signals a partial (incremental) recompute doesn't
        # supply, so it doesn't clobber values a full sync captured.
        if has_releases is None or vulnerabilities is None:
            prior_summary = (await self._metrics_store.get(repository.id) or {}).get("summary", {})
            if has_releases is None:
                has_releases = prior_summary.get("has_releases")
            if vulnerabilities is None:
                vulnerabilities = prior_summary.get("vulnerabilities")
        issues = await self._issues.list_by_repository(repository.id)
        prs = await self._pull_requests.list_by_repository(repository.id)
        documents = await self._documents.list_by_repository(repository.id)
        openspec_changes = await self._openspec.list_by_repository(repository.id)

        issue_metrics = self._issue_metrics.compute(issues, now)
        pr_metrics = self._pr_metrics.compute(prs, now)
        doc_types = {d.type for d in documents}
        summary = {
            "full_name": str(repository.full_name),
            "description": repository.description,
            "primary_language": repository.primary_language,
            "default_branch": repository.default_branch,
            "indexing_mode": repository.indexing_mode.value,
            "has_readme": DocumentType.README in doc_types,
            "has_docs": DocumentType.DOCS in doc_types,
            "has_openspec": bool(openspec_changes) or DocumentType.OPENSPEC in doc_types,
            "documents": len(documents),
            "openspec_changes": len(openspec_changes),
            "open_issues": issue_metrics.open_count,
            "closed_issues": issue_metrics.closed_count,
            "open_prs": pr_metrics.open_count,
            "merged_prs": pr_metrics.merged_count,
            "avg_issue_resolution_seconds": issue_metrics.avg_resolution_seconds,
            "avg_pr_merge_seconds": pr_metrics.avg_time_to_merge_seconds,
            "has_releases": has_releases,
            "vulnerabilities": vulnerabilities,
        }
        await self._metrics_store.save(
            repository.id,
            issue_metrics=dict(asdict(issue_metrics)),
            pr_metrics=dict(asdict(pr_metrics)),
            summary=summary,
            computed_at=now,
        )

        if self._history is not None:
            # Health for the trend is scored portfolio-style (no file-tree read),
            # matching how PortfolioIntelligenceService scores the leaderboard.
            health = self._health.score(
                HealthInputs(
                    synced=repository.last_synced_at is not None,
                    has_readme=bool(summary["has_readme"]),
                    has_docs=bool(summary["has_docs"]),
                    has_openspec=bool(summary["has_openspec"]),
                    merged_prs=pr_metrics.merged_count,
                    median_merge_seconds=pr_metrics.median_time_to_merge_seconds,
                    merge_rate=pr_metrics.merge_rate,
                    median_issue_resolution_seconds=issue_metrics.median_resolution_seconds,
                    open_issues=issue_metrics.open_count,
                    stale_issue_count=len(issue_metrics.stale_issues),
                    open_prs=pr_metrics.open_count,
                    stale_pr_count=len(pr_metrics.stale_prs),
                    last_activity=repository.github_updated_at or repository.last_synced_at,
                    signals=RepositorySignals(),
                ),
                now,
            )
            await self._history.record(
                MetricsSnapshot(
                    repository_id=repository.id,
                    captured_on=now.date(),
                    captured_at=now,
                    open_issues=issue_metrics.open_count,
                    closed_issues=issue_metrics.closed_count,
                    open_prs=pr_metrics.open_count,
                    merged_prs=pr_metrics.merged_count,
                    median_cycle_seconds=issue_metrics.median_resolution_seconds,
                    health_overall=health.overall,
                )
            )
