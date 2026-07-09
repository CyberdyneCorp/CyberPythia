"""Capability / feature composites (spec: engineering-intelligence).

One-call, LLM-free answers to common PM/PO questions — "what does this project do",
"which capabilities does it have", "how many bugs", "what can my org do right now" —
composed from indexed OpenSpec specs, documentation, and metrics so an agent doesn't
have to orchestrate several calls.
"""

from dataclasses import dataclass
from typing import Any

from app.application.errors import UnknownResourceError
from app.application.use_cases.intelligence import MetricsReader
from app.domain.entities.repository import Repository
from app.domain.ports.persistence_ports import DocumentPort, OpenSpecPort, RepositoryPort
from app.domain.services.intelligence_rules import bug_label_count
from app.domain.value_objects.enums import DocumentType

_MAX_TOPICS = 20


@dataclass(slots=True)
class CapabilitiesService:
    repositories: RepositoryPort
    documents: DocumentPort
    openspec: OpenSpecPort
    metrics: MetricsReader

    async def _repo(self, full_name: str) -> Repository:
        repo = await self.repositories.get_by_full_name(full_name)
        if repo is None or not repo.enabled:
            raise UnknownResourceError(f"repository '{full_name}' is not indexed")
        return repo

    async def _capabilities_of(self, repo: Repository) -> dict[str, Any]:
        changes = await self.openspec.list_by_repository(repo.id)
        capabilities = sorted({spec for c in changes for spec in c.affected_specs})
        docs = await self.documents.list_by_repository(repo.id)
        topics = [d.title for d in docs if d.title][:_MAX_TOPICS]
        metrics = await self.metrics.get(repo.id)
        im = (metrics or {}).get("issue_metrics", {})
        pm = (metrics or {}).get("pr_metrics", {})
        return {
            "full_name": str(repo.full_name),
            "description": repo.description,
            "primary_language": repo.primary_language,
            "capabilities": capabilities,  # OpenSpec spec areas
            "openspec_changes": len(changes),
            "documentation_topics": topics,
            "documents": len(docs),
            "issues": {
                "open": int(im.get("open_count", 0)),
                "closed": int(im.get("closed_count", 0)),
                "bugs": bug_label_count(dict(im.get("by_label", {}))),
            },
            "pull_requests": {
                "open": int(pm.get("open_count", 0)),
                "merged": int(pm.get("merged_count", 0)),
            },
        }

    async def repository_capabilities(self, full_name: str) -> dict[str, Any]:
        return await self._capabilities_of(await self._repo(full_name))

    async def repository_capabilities_by_id(self, repository_id: Any) -> dict[str, Any]:
        repo = await self.repositories.get(repository_id)
        if repo is None or not repo.enabled:
            raise UnknownResourceError(f"repository {repository_id} is not indexed")
        return await self._capabilities_of(repo)

    async def organization_openspec_coverage(self, organization: str) -> dict[str, Any]:
        """Partition an org's indexed repositories into those with / missing OpenSpec.

        Uses the canonical `has_openspec` signal from the latest sync (indexed OpenSpec
        changes or an OpenSpec-type document). Never-synced repos have no signal and are
        reported under `without_openspec` with a null `last_synced_at`.
        """
        owner = organization.lower()
        repos = [
            r
            for r in await self.repositories.list_all(enabled_only=True)
            if r.full_name.owner.lower() == owner
        ]
        with_os: list[dict[str, Any]] = []
        without_os: list[dict[str, Any]] = []
        for r in repos:
            changes = await self.openspec.list_by_repository(r.id)
            docs = await self.documents.list_by_repository(r.id)
            # canonical signal: indexed OpenSpec changes OR an OpenSpec-type document
            has = bool(changes) or any(d.type is DocumentType.OPENSPEC for d in docs)
            brief = {
                "repository_id": str(r.id),
                "full_name": str(r.full_name),
                "primary_language": r.primary_language,
                "openspec_changes": len(changes),
                "last_synced_at": r.last_synced_at.isoformat() if r.last_synced_at else None,
            }
            (with_os if has else without_os).append(brief)
        return {
            "organization": organization,
            "total": len(repos),
            "with_openspec": with_os,
            "without_openspec": without_os,
            "coverage": round(len(with_os) / len(repos), 3) if repos else 0.0,
        }

    async def organization_capabilities(self, organization: str) -> dict[str, Any]:
        owner = organization.lower()
        repos = [
            r
            for r in await self.repositories.list_all(enabled_only=True)
            if r.full_name.owner.lower() == owner
        ]
        projects = [await self._capabilities_of(r) for r in repos]
        capabilities = sorted({c for p in projects for c in p["capabilities"]})
        return {
            "organization": organization,
            "repositories": len(projects),
            "capabilities": capabilities,  # union across the org
            "total_open_bugs": sum(p["issues"]["bugs"] for p in projects),
            "projects": projects,
        }
