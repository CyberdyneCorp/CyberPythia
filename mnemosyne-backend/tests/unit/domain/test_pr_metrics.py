from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.domain.entities.pull_request import PullRequest
from app.domain.services.pr_metrics import PullRequestMetricsService, size_bucket
from app.domain.value_objects.enums import PullRequestState

NOW = datetime(2026, 7, 7, 12, 0, tzinfo=UTC)


def pr(number, *, state=PullRequestState.OPEN, merged=False, created_days_ago=2, **kw):
    return PullRequest(
        id=uuid4(),
        repository_id=uuid4(),
        github_pr_id=number,
        number=number,
        title=f"pr {number}",
        body=None,
        state=state,
        merged=merged,
        author=kw.pop("author", "bob"),
        created_at=NOW - timedelta(days=created_days_ago),
        **kw,
    )


class TestMergeMetrics:
    def test_avg_median_merge_time_over_merged_only(self):
        prs = [
            pr(1, state=PullRequestState.MERGED, merged=True, created_days_ago=4,
               merged_at=NOW - timedelta(days=2)),  # 2d
            pr(2, state=PullRequestState.MERGED, merged=True, created_days_ago=6,
               merged_at=NOW),  # 6d
            pr(3),  # open, excluded
            pr(4, state=PullRequestState.CLOSED),  # closed unmerged, excluded from times
        ]
        m = PullRequestMetricsService().compute(prs, NOW)
        assert m.avg_time_to_merge_seconds == timedelta(days=4).total_seconds()
        assert m.median_time_to_merge_seconds == timedelta(days=4).total_seconds()
        assert m.merge_rate == pytest.approx(2 / 3)  # merged / finished

    def test_absent_not_zero(self):
        m = PullRequestMetricsService().compute([pr(1)], NOW)
        assert m.avg_time_to_merge_seconds is None
        assert m.merge_rate is None
        assert m.avg_time_to_first_review_seconds is None


class TestReviewMetrics:
    def test_unreviewed_prs_excluded_from_first_review_avg(self):
        prs = [
            pr(1, first_review_at=NOW - timedelta(days=1)),  # 1d to review
            pr(2),  # no review: excluded
        ]
        m = PullRequestMetricsService().compute(prs, NOW)
        assert m.avg_time_to_first_review_seconds == timedelta(days=1).total_seconds()


class TestSizeAndStaleness:
    @pytest.mark.parametrize(
        ("lines", "bucket"),
        [(0, "XS"), (10, "XS"), (11, "S"), (100, "S"), (500, "M"), (999, "L"), (5000, "XL")],
    )
    def test_size_buckets(self, lines, bucket):
        assert size_bucket(lines) == bucket

    def test_size_distribution_and_stale(self):
        prs = [
            pr(1, additions=5, deletions=0, created_days_ago=60,
               updated_at=NOW - timedelta(days=45)),
            pr(2, additions=600, deletions=0),
        ]
        m = PullRequestMetricsService(stale_threshold_days=30).compute(prs, NOW)
        assert m.size_distribution == {"XS": 1, "L": 1}
        assert [s.number for s in m.stale_prs] == [1]


class TestBreakdowns:
    def test_by_author_and_reviewer(self):
        prs = [
            pr(1, author="bob", reviewers=["carol"]),
            pr(2, author="bob", reviewers=["carol", "dave"]),
        ]
        m = PullRequestMetricsService().compute(prs, NOW)
        assert m.by_author == {"bob": 2}
        assert m.by_reviewer == {"carol": 2, "dave": 1}
