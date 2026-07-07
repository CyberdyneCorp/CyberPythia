from datetime import UTC, datetime, timedelta

from app.domain.services.intelligence_rules import (
    RiskLevel,
    bug_label_count,
    is_abandoned,
    is_active,
    reviewer_load_concentration,
    risk_level,
)

NOW = datetime(2026, 7, 7, tzinfo=UTC)


def test_reviewer_concentration() -> None:
    assert reviewer_load_concentration({"a": 8, "b": 2}) == 0.8
    assert reviewer_load_concentration({}) is None
    assert reviewer_load_concentration({"a": 0}) is None


def test_abandoned_and_active_windows() -> None:
    assert is_abandoned(NOW - timedelta(days=200), NOW) is True
    assert is_abandoned(NOW - timedelta(days=10), NOW) is False
    assert is_abandoned(None, NOW) is False
    assert is_active(NOW - timedelta(days=5), NOW) is True
    assert is_active(NOW - timedelta(days=90), NOW) is False
    assert is_active(None, NOW) is False


def test_bug_label_count_case_insensitive() -> None:
    assert bug_label_count({"Bug": 3, "feature": 5, "regression": 2}) == 5
    assert bug_label_count({"enhancement": 4}) == 0


def test_risk_levels() -> None:
    assert risk_level(0) is RiskLevel.LOW
    assert risk_level(2) is RiskLevel.MEDIUM
    assert risk_level(3) is RiskLevel.HIGH
