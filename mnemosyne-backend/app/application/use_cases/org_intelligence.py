"""Organization-level intelligence rollup (spec: engineering-intelligence).

A pure aggregation over an org-scoped portfolio + delivery scorecard, so agents
can answer "how is this organization doing overall?" in one call instead of
looping every repository.
"""

from statistics import mean, median
from typing import Any

from app.application.dto.delivery import DeliveryScorecardEntry
from app.application.dto.intelligence import PortfolioOverview


def build_org_intelligence(
    organization: str,
    portfolio: PortfolioOverview,
    scorecard: list[DeliveryScorecardEntry],
) -> dict[str, Any]:
    """Aggregate an org-scoped portfolio + scorecard into a single rollup dict.

    Inputs must already be filtered to the organization. Absent data stays
    absent — averages are ``None`` when no repository has a health score.
    """
    scores = [p.overall for p in portfolio.leaderboard if p.has_data and p.overall is not None]
    grades: dict[str, int] = {}
    for p in portfolio.leaderboard:
        if p.grade:
            grades[p.grade] = grades.get(p.grade, 0) + 1

    directions: dict[str, int] = {}
    for s in scorecard:
        if s.throughput_direction:
            directions[s.throughput_direction] = directions.get(s.throughput_direction, 0) + 1

    return {
        "organization": organization,
        "total_repositories": portfolio.total_repositories,
        "scored": portfolio.scored,
        "average_health": round(mean(scores), 1) if scores else None,
        "median_health": round(median(scores), 1) if scores else None,
        "grade_distribution": grades,
        "at_risk_milestones": sum(e.at_risk_milestones for e in scorecard),
        "throughput_directions": directions,  # {"up": n, "down": n, "flat": n}
        "backlog_shrinking_repos": sum(1 for e in scorecard if e.backlog_shrinking),
        "most_active": portfolio.most_active,
        "abandoned": portfolio.abandoned,
        "bug_heavy": portfolio.bug_heavy,
    }
