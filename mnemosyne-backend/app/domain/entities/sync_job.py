"""Sync job entity: one asynchronous sync run for a repository."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.domain.value_objects.enums import IndexingMode, SyncStatus, SyncStep


class SyncConflictError(Exception):
    """A sync is already running for the repository (spec: repository-sync)."""


@dataclass(slots=True)
class SyncStepResult:
    step: SyncStep
    status: SyncStatus = SyncStatus.PENDING
    error: str | None = None
    items_processed: int = 0


@dataclass(slots=True)
class SyncJob:
    id: UUID
    repository_id: UUID
    mode: IndexingMode
    status: SyncStatus = SyncStatus.PENDING
    steps: list[SyncStepResult] = field(default_factory=list)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    triggered_by: str | None = None  # caller subject, for auditing

    @staticmethod
    def steps_for_mode(mode: IndexingMode) -> list[SyncStep]:
        """Which steps a sync runs, honoring the indexing mode (spec: repository-sync)."""
        steps = [SyncStep.METADATA, SyncStep.DOCS, SyncStep.OPENSPEC]
        if mode.includes_issues_and_prs:
            steps += [SyncStep.ISSUES, SyncStep.PULL_REQUESTS]
        if mode.includes_file_tree:
            steps += [SyncStep.FILE_TREE]
        steps += [SyncStep.EMBEDDINGS, SyncStep.METRICS]
        return steps

    def plan(self) -> None:
        self.steps = [SyncStepResult(step=s) for s in self.steps_for_mode(self.mode)]

    def start(self, at: datetime) -> None:
        self.status = SyncStatus.RUNNING
        self.started_at = at

    def step_result(self, step: SyncStep) -> SyncStepResult:
        for result in self.steps:
            if result.step is step:
                return result
        raise KeyError(f"step {step} not planned for this job")

    def record_step(
        self, step: SyncStep, status: SyncStatus, *, error: str | None = None, items: int = 0
    ) -> None:
        result = self.step_result(step)
        result.status = status
        result.error = error
        result.items_processed = items

    def finish(self, at: datetime) -> None:
        """Job fails if any step failed; successful steps' data is retained."""
        self.finished_at = at
        failed = any(s.status is SyncStatus.FAILED for s in self.steps)
        self.status = SyncStatus.FAILED if failed else SyncStatus.SUCCEEDED

    @property
    def failed_steps(self) -> list[SyncStepResult]:
        return [s for s in self.steps if s.status is SyncStatus.FAILED]
