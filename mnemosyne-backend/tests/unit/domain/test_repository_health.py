from datetime import UTC, datetime, timedelta

from app.domain.services.repository_health import RepositoryHealthService
from app.domain.value_objects.health import Grade, HealthInputs, RepositorySignals

svc = RepositoryHealthService()
NOW = datetime(2026, 7, 7, tzinfo=UTC)


def _inputs(**over: object) -> HealthInputs:
    base: dict[str, object] = dict(
        synced=True,
        has_readme=True,
        has_docs=True,
        has_openspec=True,
        merged_prs=10,
        median_merge_seconds=86400.0,
        merge_rate=0.9,
        median_issue_resolution_seconds=2 * 86400.0,
        open_issues=5,
        stale_issue_count=0,
        open_prs=2,
        stale_pr_count=0,
        last_activity=NOW - timedelta(days=1),
        signals=RepositorySignals(has_ci=True, has_tests=True),
    )
    base.update(over)
    return HealthInputs(**base)  # type: ignore[arg-type]


def test_fully_populated_scores_high() -> None:
    health = svc.score(_inputs(), NOW)
    assert health.has_data is True
    assert health.overall is not None and health.overall >= 90
    assert health.grade is Grade.A
    assert all(c.score is not None for c in health.components)


def test_never_synced_is_insufficient_data() -> None:
    health = svc.score(_inputs(synced=False), NOW)
    assert health.has_data is False
    assert health.overall is None
    assert health.grade is None
    assert health.components == []


def test_unknown_testing_ci_excluded_and_weights_renormalise() -> None:
    health = svc.score(_inputs(signals=RepositorySignals()), NOW)
    testing = next(c for c in health.components if c.name == "testing_ci")
    assert testing.score is None
    present = [c for c in health.components if c.score is not None]
    assert sum(c.weight for c in present) < 1.0  # testing_ci weight dropped
    # overall is the renormalised mean of only the present components
    total_w = sum(c.weight for c in present)
    expected = sum(c.score * c.weight for c in present) / total_w  # type: ignore[operator]
    assert health.overall == round(expected, 1)


def test_missing_delivery_data_drops_out() -> None:
    health = svc.score(
        _inputs(merged_prs=0, merge_rate=None, median_merge_seconds=None,
                median_issue_resolution_seconds=None),
        NOW,
    )
    delivery = next(c for c in health.components if c.name == "delivery")
    assert delivery.score is None


def test_maintenance_none_when_nothing_open() -> None:
    health = svc.score(_inputs(open_issues=0, open_prs=0), NOW)
    maint = next(c for c in health.components if c.name == "maintenance")
    assert maint.score is None


def test_stale_lowers_maintenance_and_yields_finding() -> None:
    health = svc.score(_inputs(open_issues=10, open_prs=0, stale_issue_count=8), NOW)
    maint = next(c for c in health.components if c.name == "maintenance")
    assert maint.score is not None and maint.score < 30
    assert any(f.metric == "stale" for f in health.findings)


def test_findings_flag_missing_ci_and_readme() -> None:
    health = svc.score(
        _inputs(has_readme=False, signals=RepositorySignals(has_ci=False, has_tests=False)),
        NOW,
    )
    metrics = {f.metric for f in health.findings}
    assert {"has_readme", "has_ci", "has_tests"} <= metrics


def test_grade_boundaries() -> None:
    # push everything low: no docs, slow, stale, no ci/tests, stale activity
    low = svc.score(
        _inputs(
            has_readme=False, has_docs=False, has_openspec=False,
            merge_rate=0.0, median_merge_seconds=40 * 86400.0,
            median_issue_resolution_seconds=60 * 86400.0,
            open_issues=10, stale_issue_count=10,
            signals=RepositorySignals(has_ci=False, has_tests=False),
            last_activity=NOW - timedelta(days=365),
        ),
        NOW,
    )
    assert low.grade is Grade.F
