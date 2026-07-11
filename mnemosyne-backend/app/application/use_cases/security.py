"""Organization dependency-vulnerability view (spec: engineering-intelligence).

Reads the open Dependabot alert counts captured into each repository's metrics
summary snapshot during sync — no live GitHub calls at query time.
"""

from dataclasses import dataclass
from typing import Any

from app.application.use_cases.intelligence import MetricsReader
from app.domain.ports.persistence_ports import RepositoryPort


@dataclass(slots=True)
class SecurityService:
    repositories: RepositoryPort
    metrics: MetricsReader

    async def organization_vulnerabilities(self, organization: str) -> dict[str, Any]:
        owner = organization.lower()
        repos = [
            r
            for r in await self.repositories.list_all(enabled_only=True)
            if r.full_name.owner.lower() == owner
        ]
        rows: list[dict[str, Any]] = []
        total_critical = total_high = 0
        for r in repos:
            m = await self.metrics.get(r.id) or {}
            vulns = m.get("summary", {}).get("vulnerabilities")
            if not isinstance(vulns, dict):
                continue  # not captured for this repo (unknown)
            critical = int(vulns.get("critical", 0))
            high = int(vulns.get("high", 0))
            total_critical += critical
            total_high += high
            if critical or high:
                rows.append({
                    "repository_id": str(r.id),
                    "full_name": str(r.full_name),
                    "critical": critical,
                    "high": high,
                })
        rows.sort(key=lambda x: (-x["critical"], -x["high"], x["full_name"]))
        return {
            "organization": organization,
            "total_critical": total_critical,
            "total_high": total_high,
            "repositories": rows,
        }
