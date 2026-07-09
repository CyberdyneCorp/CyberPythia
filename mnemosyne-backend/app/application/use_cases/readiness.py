"""Project readiness classification service (spec: engineering-intelligence).

Gathers observable signals per repository (file tree → CI/tests/monitoring, docs,
OpenSpec, issue/PR metrics) and classifies each into MVP / READY / DONE via the pure
`classify_readiness` domain rule. Also rolls an organization up into a distribution.
"""

from dataclasses import dataclass
from typing import Any

from app.application.errors import UnknownResourceError
from app.application.use_cases.intelligence import MetricsReader
from app.domain.entities.repository import Repository
from app.domain.ports.persistence_ports import (
    DocumentPort,
    FilePort,
    OpenSpecPort,
    RepositoryPort,
)
from app.domain.services.intelligence_rules import bug_label_count
from app.domain.services.readiness import ReadinessInputs, classify_readiness
from app.domain.services.repository_signals import RepositorySignalsService
from app.domain.value_objects.enums import DocumentType


@dataclass(slots=True)
class ReadinessService:
    repositories: RepositoryPort
    files: FilePort
    documents: DocumentPort
    openspec: OpenSpecPort
    metrics: MetricsReader
    signals: RepositorySignalsService

    async def _inputs(self, repo: Repository) -> ReadinessInputs:
        paths = [f.path for f in await self.files.list_by_repository(repo.id)]
        sig = self.signals.detect(paths, repo.indexing_mode)
        doc_types = {d.type for d in await self.documents.list_by_repository(repo.id)}
        changes = await self.openspec.list_by_repository(repo.id)
        m = await self.metrics.get(repo.id) or {}
        im = m.get("issue_metrics", {})
        pm = m.get("pr_metrics", {})
        return ReadinessInputs(
            has_readme=DocumentType.README in doc_types,
            has_guide_doc=DocumentType.DOCS in doc_types,
            has_adr=DocumentType.ARCHITECTURE in doc_types,
            has_security_doc=DocumentType.SECURITY in doc_types,
            has_openspec=bool(changes) or DocumentType.OPENSPEC in doc_types,
            has_ci=sig.has_ci,
            has_tests=sig.has_tests,
            has_dependency_manifest=sig.has_dependency_manifest,
            has_dependabot=sig.has_dependabot,
            has_security_scanning=sig.has_security_scanning,
            closed_issues=int(im.get("closed_count", 0)),
            merged_prs=int(pm.get("merged_count", 0)),
            open_issues=int(im.get("open_count", 0)),
            open_bugs=bug_label_count(dict(im.get("by_label", {}))),
        )

    async def repository_readiness(self, full_name: str) -> dict[str, Any]:
        repo = await self.repositories.get_by_full_name(full_name)
        if repo is None or not repo.enabled:
            raise UnknownResourceError(f"repository '{full_name}' is not indexed")
        result = classify_readiness(await self._inputs(repo))
        return {"full_name": str(repo.full_name), "indexing_mode": repo.indexing_mode.value,
                **result}

    async def organization_readiness(self, organization: str) -> dict[str, Any]:
        owner = organization.lower()
        repos = [
            r
            for r in await self.repositories.list_all(enabled_only=True)
            if r.full_name.owner.lower() == owner
        ]
        distribution = {"MVP": 0, "READY": 0, "DONE": 0}
        rows: list[dict[str, Any]] = []
        for r in repos:
            result = classify_readiness(await self._inputs(r))
            distribution[result["gate"]] += 1
            rows.append({
                "repository_id": str(r.id),
                "full_name": str(r.full_name),
                "gate": result["gate"],
                "missing_for_ready": result["missing_for_ready"],
            })
        rows.sort(key=lambda x: ({"DONE": 0, "READY": 1, "MVP": 2}[x["gate"]], x["full_name"]))
        return {
            "organization": organization,
            "total": len(repos),
            "distribution": distribution,
            "repositories": rows,
        }
