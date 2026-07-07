from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.domain.entities.issue import Issue
from app.domain.services.issue_metrics import IssueMetricsService
from app.domain.value_objects.enums import IssueState

NOW = datetime(2026, 7, 7, 12, 0, tzinfo=UTC)


def issue(number, *, state=IssueState.OPEN, created_days_ago=1, closed_days_ago=None, **kw):
    return Issue(
        id=uuid4(),
        repository_id=uuid4(),
        github_issue_id=number,
        number=number,
        title=f"issue {number}",
        body=None,
        state=state,
        author="alice",
        created_at=NOW - timedelta(days=created_days_ago),
        closed_at=NOW - timedelta(days=closed_days_ago) if closed_days_ago is not None else None,
        **kw,
    )


class TestResolutionTimes:
    def test_avg_and_median_over_closed_only(self):
        issues = [
            issue(1, state=IssueState.CLOSED, created_days_ago=10, closed_days_ago=8),  # 2d
            issue(2, state=IssueState.CLOSED, created_days_ago=10, closed_days_ago=4),  # 6d
            issue(3, state=IssueState.CLOSED, created_days_ago=10, closed_days_ago=0),  # 10d
            issue(4, created_days_ago=100),  # open: excluded
        ]
        m = IssueMetricsService().compute(issues, NOW)
        assert m.avg_resolution_seconds == timedelta(days=6).total_seconds()
        assert m.median_resolution_seconds == timedelta(days=6).total_seconds()
        assert m.closed_count == 3 and m.open_count == 1

    def test_absent_not_zero_when_no_closed_issues(self):
        m = IssueMetricsService().compute([issue(1)], NOW)
        assert m.avg_resolution_seconds is None
        assert m.median_resolution_seconds is None

    def test_empty_population(self):
        m = IssueMetricsService().compute([], NOW)
        assert m.total == 0
        assert m.avg_resolution_seconds is None
        assert m.open_age_seconds_avg is None


class TestStaleness:
    def test_stale_detection_sorted_oldest_first(self):
        issues = [
            issue(1, created_days_ago=90, updated_at=NOW - timedelta(days=40)),
            issue(2, created_days_ago=400, updated_at=NOW - timedelta(days=300)),
            issue(3, created_days_ago=90, updated_at=NOW - timedelta(days=1)),  # active
        ]
        m = IssueMetricsService(stale_threshold_days=30).compute(issues, NOW)
        assert [s.number for s in m.stale_issues] == [2, 1]
        assert m.stale_issues[0].age_days == 400.0


class TestBreakdowns:
    def test_by_label_and_assignee(self):
        issues = [
            issue(1, labels=["bug", "p1"], assignees=["alice"]),
            issue(2, labels=["bug"], assignees=["alice", "bob"]),
        ]
        m = IssueMetricsService().compute(issues, NOW)
        assert m.by_label == {"bug": 2, "p1": 1}
        assert m.by_assignee == {"alice": 2, "bob": 1}
