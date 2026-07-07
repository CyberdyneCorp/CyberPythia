"""GitHub pull request entity."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.domain.value_objects.enums import PullRequestState


@dataclass(slots=True)
class PullRequest:
    id: UUID
    repository_id: UUID
    github_pr_id: int
    number: int
    title: str
    body: str | None
    state: PullRequestState
    merged: bool
    author: str | None
    reviewers: list[str] = field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    closed_at: datetime | None = None
    merged_at: datetime | None = None
    first_review_at: datetime | None = None
    changed_files: int = 0
    additions: int = 0
    deletions: int = 0
    review_decision: str | None = None

    @property
    def time_to_merge_seconds(self) -> float | None:
        """merged_at - created_at; only defined for merged PRs (spec: repository-sync)."""
        if self.merged and self.merged_at and self.created_at:
            return (self.merged_at - self.created_at).total_seconds()
        return None

    @property
    def time_to_first_review_seconds(self) -> float | None:
        if self.first_review_at and self.created_at:
            return (self.first_review_at - self.created_at).total_seconds()
        return None

    @property
    def total_changed_lines(self) -> int:
        return self.additions + self.deletions

    def is_stale(self, now: datetime, threshold_days: int) -> bool:
        if self.state is not PullRequestState.OPEN:
            return False
        reference = self.updated_at or self.created_at
        if reference is None:
            return False
        return (now - reference).days > threshold_days
