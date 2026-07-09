"""Engineering-intelligence value objects (spec: engineering-intelligence).

Absent-not-zero: a component with no inputs is ``None`` (excluded from the
weighted overall), never a fabricated 0. File-tree signals are ``None`` = unknown
when the indexing mode captures no tree.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


@dataclass(frozen=True, slots=True)
class RepositorySignals:
    """Presence signals derived from the captured file tree.

    Each flag is ``True``/``False`` when the tree was captured, or ``None`` when
    the indexing mode captures no tree (unknown, never counted against a score).
    """

    has_ci: bool | None = None
    has_tests: bool | None = None
    has_dependency_manifest: bool | None = None
    has_contributing: bool | None = None
    has_license: bool | None = None
    has_dependabot: bool | None = None  # .github/dependabot.yml
    has_security_scanning: bool | None = None  # CodeQL / Semgrep workflow


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class HealthFinding:
    """One reason the score is what it is."""

    severity: Severity
    message: str
    metric: str


@dataclass(frozen=True, slots=True)
class ComponentScore:
    """A single health dimension: 0-100, or ``None`` when its inputs are absent."""

    name: str
    weight: float
    score: float | None
    inputs: dict[str, object] = field(default_factory=dict)


class Grade(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"


def grade_for(overall: float | None) -> Grade | None:
    if overall is None:
        return None
    if overall >= 90:
        return Grade.A
    if overall >= 75:
        return Grade.B
    if overall >= 60:
        return Grade.C
    if overall >= 40:
        return Grade.D
    return Grade.F


@dataclass(frozen=True, slots=True)
class RepositoryHealth:
    """A repository's health: component breakdown, renormalised overall, findings."""

    components: list[ComponentScore]
    overall: float | None
    grade: Grade | None
    findings: list[HealthFinding] = field(default_factory=list)
    has_data: bool = True


@dataclass(frozen=True, slots=True)
class HealthInputs:
    """Everything the health service needs, assembled from persisted metrics.

    Keeps scoring pure and decoupled from storage: the application layer builds
    this from a ``repository_metrics`` row (or live metric dataclasses).
    """

    synced: bool
    has_readme: bool
    has_docs: bool
    has_openspec: bool
    merged_prs: int
    median_merge_seconds: float | None
    merge_rate: float | None
    median_issue_resolution_seconds: float | None
    open_issues: int
    stale_issue_count: int
    open_prs: int
    stale_pr_count: int
    last_activity: datetime | None
    signals: RepositorySignals
