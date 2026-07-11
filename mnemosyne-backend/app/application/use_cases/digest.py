"""Organization attention digest (spec: engineering-intelligence).

Assembles the already-computed "needs attention" signals — readiness
regressions, oldest stale issues/PRs, at-risk milestones — into one payload with
a human-readable summary, for pull (REST/MCP) and push (daily webhook delivery).
"""

from dataclasses import dataclass
from typing import Any

from app.application.use_cases.cross_repo import CrossRepoService
from app.application.use_cases.delivery_intelligence import DeliveryIntelligenceService
from app.application.use_cases.readiness import ReadinessService

_STALE_LIMIT = 10


@dataclass(slots=True)
class DigestService:
    readiness: ReadinessService
    cross_repo: CrossRepoService
    delivery: DeliveryIntelligenceService

    async def build(self, organization: str) -> dict[str, Any]:
        regressions = (await self.readiness.organization_regressions(organization))["regressions"]
        stale_issues = await self.cross_repo.find_stale_issues(
            organization=organization, limit=_STALE_LIMIT)
        stale_prs = await self.cross_repo.find_stale_prs(
            organization=organization, limit=_STALE_LIMIT)
        scorecard = await self.delivery.delivery_scorecard(organization=organization)
        at_risk = sum(e.at_risk_milestones for e in scorecard)

        summary = (
            f"{organization}: {len(regressions)} readiness regression(s), "
            f"{len(stale_issues)} stale issue(s), {len(stale_prs)} stale PR(s), "
            f"{at_risk} at-risk milestone(s)"
        )
        return {
            "organization": organization,
            "summary": summary,
            "text": summary,  # Slack-compatible top-level field
            "regressions": regressions,
            "stale_issues": stale_issues,
            "stale_prs": stale_prs,
            "at_risk_milestones": at_risk,
            "is_empty": not (regressions or stale_issues or stale_prs or at_risk),
        }
