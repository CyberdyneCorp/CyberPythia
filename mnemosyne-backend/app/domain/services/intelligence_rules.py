"""Shared pure thresholds/rankings for engineering-intelligence analytics.

Kept separate from the analytics application services so the judgement (windows,
concentration, risk levels) is unit-testable in isolation (spec:
engineering-intelligence).
"""

from datetime import datetime, timedelta
from enum import StrEnum

# Windows / thresholds (documented constants).
ABANDONED_AFTER_DAYS = 180
ACTIVE_WITHIN_DAYS = 30
STALE_SYNC_AFTER_DAYS = 14
HIGH_BACKLOG_OPEN_ISSUES = 40
BUG_LABELS = frozenset({"bug", "defect", "regression"})


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


def reviewer_load_concentration(by_reviewer: dict[str, int]) -> float | None:
    """Top-reviewer share of all reviews (0-1); ``None`` when there are no reviews.

    1.0 means one reviewer carries everything (a bottleneck); lower is healthier.
    """
    total = sum(by_reviewer.values())
    if total <= 0:
        return None
    return max(by_reviewer.values()) / total


def is_abandoned(last_activity: datetime | None, now: datetime) -> bool:
    if last_activity is None:
        return False
    return (now - last_activity) >= timedelta(days=ABANDONED_AFTER_DAYS)


def is_active(last_activity: datetime | None, now: datetime) -> bool:
    if last_activity is None:
        return False
    return (now - last_activity) <= timedelta(days=ACTIVE_WITHIN_DAYS)


def bug_label_count(by_label: dict[str, int]) -> int:
    return sum(count for label, count in by_label.items() if label.lower() in BUG_LABELS)


def risk_level(reason_count: int) -> RiskLevel:
    if reason_count >= 3:
        return RiskLevel.HIGH
    if reason_count >= 1:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW
