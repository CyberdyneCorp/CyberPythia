"""GitHub issue entity."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.domain.value_objects.enums import IssueState


@dataclass(slots=True)
class Issue:
    id: UUID
    repository_id: UUID
    github_issue_id: int
    number: int
    title: str
    body: str | None
    state: IssueState
    author: str | None
    labels: list[str] = field(default_factory=list)
    assignees: list[str] = field(default_factory=list)
    milestone: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    closed_at: datetime | None = None
    comments_count: int = 0
    first_response_at: datetime | None = None
    reopened_count: int = 0

    @property
    def first_response_seconds(self) -> float | None:
        """created_at -> first non-author response; None when not captured."""
        if self.first_response_at is None or self.created_at is None:
            return None
        return (self.first_response_at - self.created_at).total_seconds()

    @property
    def resolution_time_seconds(self) -> float | None:
        """closed_at - created_at; only defined for closed issues (spec: repository-sync)."""
        if self.state is IssueState.CLOSED and self.closed_at and self.created_at:
            return (self.closed_at - self.created_at).total_seconds()
        return None

    def age_seconds(self, now: datetime) -> float | None:
        if self.created_at is None:
            return None
        return (now - self.created_at).total_seconds()

    def is_stale(self, now: datetime, threshold_days: int) -> bool:
        """Open with no activity beyond the threshold (spec: engineering-metrics)."""
        if self.state is not IssueState.OPEN:
            return False
        reference = self.updated_at or self.created_at
        if reference is None:
            return False
        return (now - reference).days > threshold_days
