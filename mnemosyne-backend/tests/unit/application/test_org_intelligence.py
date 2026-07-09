"""Unit tests for the organization intelligence rollup (spec: engineering-intelligence)."""

from app.application.dto.delivery import DeliveryScorecardEntry
from app.application.dto.intelligence import PortfolioEntry, PortfolioOverview
from app.application.use_cases.org_intelligence import build_org_intelligence


def _entry(name, overall, grade, has_data=True) -> PortfolioEntry:
    return PortfolioEntry(
        repository_id=name, full_name=name, has_data=has_data, overall=overall, grade=grade
    )


def _score(name, *, direction=None, backlog=None, at_risk=0, has_data=True) -> DeliveryScorecardEntry:
    return DeliveryScorecardEntry(
        repository_id=name, full_name=name, has_data=has_data, median_cycle_days=None,
        throughput_direction=direction, backlog_shrinking=backlog, at_risk_milestones=at_risk,
    )


def _portfolio(entries, **kw) -> PortfolioOverview:
    return PortfolioOverview(
        total_repositories=kw.get("total", len(entries)),
        scored=sum(1 for e in entries if e.has_data),
        leaderboard=entries,
        most_active=kw.get("most_active", []),
        abandoned=kw.get("abandoned", []),
        bug_heavy=kw.get("bug_heavy", []),
    )


def test_rollup_aggregates_health_and_delivery():
    portfolio = _portfolio(
        [
            _entry("org/a", 90, "A"),
            _entry("org/b", 70, "C"),
            _entry("org/c", None, None, has_data=False),
        ],
        most_active=["org/a"], bug_heavy=["org/b"],
    )
    scorecard = [
        _score("org/a", direction="up", backlog=True, at_risk=2),
        _score("org/b", direction="flat", backlog=False, at_risk=1),
    ]
    r = build_org_intelligence("org", portfolio, scorecard)
    assert r["organization"] == "org"
    assert r["total_repositories"] == 3
    assert r["scored"] == 2
    assert r["average_health"] == 80.0  # mean(90, 70)
    assert r["median_health"] == 80.0
    assert r["grade_distribution"] == {"A": 1, "C": 1}
    assert r["at_risk_milestones"] == 3
    assert r["throughput_directions"] == {"up": 1, "flat": 1}
    assert r["backlog_shrinking_repos"] == 1
    assert r["most_active"] == ["org/a"] and r["bug_heavy"] == ["org/b"]


def test_rollup_absent_when_nothing_scored():
    portfolio = _portfolio([_entry("org/a", None, None, has_data=False)])
    r = build_org_intelligence("org", portfolio, [])
    assert r["scored"] == 0
    assert r["average_health"] is None and r["median_health"] is None
    assert r["grade_distribution"] == {}
    assert r["at_risk_milestones"] == 0
