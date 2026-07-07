"""GitHub milestone entity (spec: repository-sync, delivery-intelligence)."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(slots=True)
class Milestone:
    id: UUID
    repository_id: UUID
    number: int
    title: str
    state: str  # "open" | "closed"
    due_on: datetime | None
    open_issues: int
    closed_issues: int
    updated_at: datetime | None = None

    @property
    def total_issues(self) -> int:
        return self.open_issues + self.closed_issues

    @property
    def percent_complete(self) -> float | None:
        total = self.total_issues
        return round(100.0 * self.closed_issues / total, 1) if total else None
