"""DTOs for engineering-intelligence analytics (spec: engineering-intelligence)."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class DeliveryMetrics:
    has_data: bool
    merged_prs: int
    closed_issues: int
    merge_rate: float | None
    median_merge_seconds: float | None
    median_issue_resolution_seconds: float | None
    pr_size_distribution: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StaleItem:
    number: int
    title: str
    age_days: float


@dataclass(frozen=True, slots=True)
class BacklogMetrics:
    has_data: bool
    open_issues: int
    closed_issues: int
    open_to_closed_ratio: float | None
    stale_issue_count: int
    oldest_open_age_days: float | None
    stale_issues: list[StaleItem] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ReviewBottlenecks:
    has_data: bool
    stale_pr_count: int
    reviewer_load_concentration: float | None
    stale_prs: list[StaleItem] = field(default_factory=list)
    by_reviewer: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MaintenanceRisk:
    has_data: bool
    level: str
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class PortfolioEntry:
    repository_id: str
    full_name: str
    has_data: bool
    overall: float | None
    grade: str | None


@dataclass(frozen=True, slots=True)
class PortfolioOverview:
    total_repositories: int
    scored: int
    leaderboard: list[PortfolioEntry] = field(default_factory=list)
    most_active: list[str] = field(default_factory=list)
    abandoned: list[str] = field(default_factory=list)
    bug_heavy: list[str] = field(default_factory=list)
