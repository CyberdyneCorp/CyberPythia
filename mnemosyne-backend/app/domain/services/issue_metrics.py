"""Issue metrics computation (spec: engineering-metrics).

Absent-not-zero rule: metrics over an empty population are None.
"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from statistics import mean, median

from app.domain.entities.issue import Issue
from app.domain.value_objects.enums import IssueState


@dataclass(frozen=True, slots=True)
class StaleIssue:
    number: int
    title: str
    age_days: float


@dataclass(frozen=True, slots=True)
class IssueMetrics:
    total: int
    open_count: int
    closed_count: int
    avg_resolution_seconds: float | None
    median_resolution_seconds: float | None
    open_age_seconds_avg: float | None
    stale_issues: list[StaleIssue] = field(default_factory=list)
    by_label: dict[str, int] = field(default_factory=dict)
    by_assignee: dict[str, int] = field(default_factory=dict)


class IssueMetricsService:
    def __init__(self, stale_threshold_days: int = 30) -> None:
        self._stale_threshold_days = stale_threshold_days

    def compute(self, issues: list[Issue], now: datetime) -> IssueMetrics:
        open_issues = [i for i in issues if i.state is IssueState.OPEN]
        resolution_times = [
            t for i in issues if (t := i.resolution_time_seconds) is not None
        ]
        open_ages = [a for i in open_issues if (a := i.age_seconds(now)) is not None]

        stale = sorted(
            (
                StaleIssue(
                    number=i.number,
                    title=i.title,
                    age_days=round((a or 0) / 86400, 1),
                )
                for i in open_issues
                if i.is_stale(now, self._stale_threshold_days)
                and (a := i.age_seconds(now)) is not None
            ),
            key=lambda s: -s.age_days,
        )

        by_label: Counter[str] = Counter()
        by_assignee: Counter[str] = Counter()
        for issue in issues:
            by_label.update(issue.labels)
            by_assignee.update(issue.assignees)

        return IssueMetrics(
            total=len(issues),
            open_count=len(open_issues),
            closed_count=len(issues) - len(open_issues),
            avg_resolution_seconds=mean(resolution_times) if resolution_times else None,
            median_resolution_seconds=median(resolution_times) if resolution_times else None,
            open_age_seconds_avg=mean(open_ages) if open_ages else None,
            stale_issues=stale,
            by_label=dict(by_label),
            by_assignee=dict(by_assignee),
        )
