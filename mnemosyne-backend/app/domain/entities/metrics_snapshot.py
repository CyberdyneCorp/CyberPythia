"""Metrics time-series snapshot (spec: metrics-history)."""

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class MetricsSnapshot:
    repository_id: UUID
    captured_on: date  # one row per repository per UTC day
    captured_at: datetime
    open_issues: int
    closed_issues: int
    open_prs: int
    merged_prs: int
    median_cycle_seconds: float | None
    health_overall: float | None
