"""DTOs for PM/PO delivery analytics (spec: delivery-intelligence)."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class PercentileBlock:
    n: int
    p50: float | None
    p85: float | None
    p95: float | None


@dataclass(frozen=True, slots=True)
class FlowMetrics:
    has_data: bool
    resolution_seconds: PercentileBlock
    merge_seconds: PercentileBlock
    wip_issues: int
    wip_prs: int
    issue_aging: dict[str, int] = field(default_factory=dict)
    pr_aging: dict[str, int] = field(default_factory=dict)
    untriaged_issues: int = 0


@dataclass(frozen=True, slots=True)
class TrendPoint:
    date: str
    closed_issues: int
    open_issues: int
    net_flow: int


@dataclass(frozen=True, slots=True)
class ThroughputTrend:
    has_data: bool
    points: list[TrendPoint] = field(default_factory=list)
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class BacklogForecast:
    has_data: bool
    open_issues: int
    close_rate_per_day: float | None
    projected_days_to_clear: float | None
    projected_clear_date: str | None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class WorkMix:
    has_data: bool
    distribution: dict[str, int] = field(default_factory=dict)
    bug_ratio: float | None = None


@dataclass(frozen=True, slots=True)
class QualitySignals:
    has_data: bool
    bug_ratio: float | None
    reopened_rate: float | None
    first_response_seconds: PercentileBlock | None


@dataclass(frozen=True, slots=True)
class MilestoneProgress:
    number: int
    title: str
    state: str
    percent_complete: float | None
    open_issues: int
    closed_issues: int
    due_on: str | None
    projected_completion: str | None
    at_risk: bool


@dataclass(frozen=True, slots=True)
class TeamLoad:
    has_data: bool
    open_by_assignee: dict[str, int] = field(default_factory=dict)
    reviews_by_reviewer: dict[str, int] = field(default_factory=dict)
    bus_factor: int | None = None


@dataclass(frozen=True, slots=True)
class DeliveryScorecardEntry:
    repository_id: str
    full_name: str
    has_data: bool
    median_cycle_days: float | None
    throughput_direction: str | None  # "up" | "down" | "flat" | None
    backlog_shrinking: bool | None
    at_risk_milestones: int
