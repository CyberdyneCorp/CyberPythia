"""Pull-request metrics computation (spec: engineering-metrics)."""

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from statistics import mean, median

from app.domain.entities.pull_request import PullRequest
from app.domain.value_objects.enums import PullRequestState

SIZE_BUCKETS: list[tuple[str, int]] = [
    ("XS", 10),
    ("S", 100),
    ("M", 500),
    ("L", 1000),
]  # anything larger is XL


def size_bucket(total_changed_lines: int) -> str:
    for name, limit in SIZE_BUCKETS:
        if total_changed_lines <= limit:
            return name
    return "XL"


@dataclass(frozen=True, slots=True)
class StalePullRequest:
    number: int
    title: str
    age_days: float


@dataclass(frozen=True, slots=True)
class PullRequestMetrics:
    total: int
    open_count: int
    merged_count: int
    avg_time_to_merge_seconds: float | None
    median_time_to_merge_seconds: float | None
    avg_time_to_first_review_seconds: float | None
    merge_rate: float | None  # merged / closed-or-merged
    size_distribution: dict[str, int] = field(default_factory=dict)
    stale_prs: list[StalePullRequest] = field(default_factory=list)
    by_author: dict[str, int] = field(default_factory=dict)
    by_reviewer: dict[str, int] = field(default_factory=dict)


class PullRequestMetricsService:
    def __init__(self, stale_threshold_days: int = 30) -> None:
        self._stale_threshold_days = stale_threshold_days

    def compute(self, prs: list[PullRequest], now: datetime) -> PullRequestMetrics:
        merged = [p for p in prs if p.merged]
        open_prs = [p for p in prs if p.state is PullRequestState.OPEN]
        finished = [p for p in prs if p.state is not PullRequestState.OPEN]

        merge_times = [t for p in merged if (t := p.time_to_merge_seconds) is not None]
        # PRs without any review are excluded from this average (spec)
        review_times = [t for p in prs if (t := p.time_to_first_review_seconds) is not None]

        stale = sorted(
            (
                StalePullRequest(
                    number=p.number,
                    title=p.title,
                    age_days=round((now - p.created_at).total_seconds() / 86400, 1),
                )
                for p in open_prs
                if p.is_stale(now, self._stale_threshold_days) and p.created_at is not None
            ),
            key=lambda s: -s.age_days,
        )

        by_author: Counter[str] = Counter(p.author for p in prs if p.author)
        by_reviewer: Counter[str] = Counter(r for p in prs for r in p.reviewers)
        sizes: Counter[str] = Counter(size_bucket(p.total_changed_lines) for p in prs)

        return PullRequestMetrics(
            total=len(prs),
            open_count=len(open_prs),
            merged_count=len(merged),
            avg_time_to_merge_seconds=mean(merge_times) if merge_times else None,
            median_time_to_merge_seconds=median(merge_times) if merge_times else None,
            avg_time_to_first_review_seconds=mean(review_times) if review_times else None,
            merge_rate=len(merged) / len(finished) if finished else None,
            size_distribution=dict(sizes),
            stale_prs=stale,
            by_author=dict(by_author),
            by_reviewer=dict(by_reviewer),
        )
