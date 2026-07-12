"""Agent-writable memory use case (spec: agent-memory).

The first agent-facing write surface. Memories are durable notes scoped to a
repository or organization; they are written only to Mnemosyne's own store,
never to GitHub. Recall lists a scope newest-first with optional kind/text
filters; forget deletes by id.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.application.errors import UnknownResourceError
from app.domain.entities.agent_memory import AgentMemory
from app.domain.ports.persistence_ports import MemoryPort, RepositoryPort
from app.domain.services.org_scope import is_organization_allowed, is_unrestricted


def _view(m: AgentMemory) -> dict[str, Any]:
    return {
        "id": str(m.id),
        "content": m.content,
        "kind": m.kind,
        "author": m.author,
        "created_at": m.created_at.isoformat(),
        "repository_id": str(m.repository_id) if m.repository_id else None,
        "organization": m.organization,
    }


@dataclass(slots=True)
class MemoryService:
    memories: MemoryPort
    repositories: RepositoryPort

    async def remember_repository(
        self, full_name: str, *, content: str, kind: str, author: str
    ) -> dict[str, Any]:
        repo = await self.repositories.get_by_full_name(full_name)
        if repo is None or not repo.enabled:
            raise UnknownResourceError(f"repository '{full_name}' is not indexed")
        return await self._save(content=content, kind=kind, author=author, repository_id=repo.id)

    async def remember_organization(
        self, organization: str, *, content: str, kind: str, author: str
    ) -> dict[str, Any]:
        if not is_organization_allowed(organization):
            raise UnknownResourceError(f"organization '{organization}' is not accessible")
        return await self._save(
            content=content, kind=kind, author=author, organization=organization
        )

    async def _save(
        self, *, content: str, kind: str, author: str,
        repository_id: UUID | None = None, organization: str | None = None,
    ) -> dict[str, Any]:
        memory = AgentMemory(
            id=uuid4(), content=content.strip(), kind=(kind or "note").strip() or "note",
            author=author, created_at=datetime.now(UTC),
            repository_id=repository_id, organization=organization,
        )
        await self.memories.save(memory)
        return _view(memory)

    async def recall_repository(
        self, full_name: str, *, query: str | None = None,
        kind: str | None = None, limit: int = 50,
    ) -> dict[str, Any]:
        repo = await self.repositories.get_by_full_name(full_name)
        if repo is None or not repo.enabled:
            raise UnknownResourceError(f"repository '{full_name}' is not indexed")
        rows = await self.memories.list_for_repository(
            repo.id, kind=kind, query=query, limit=limit
        )
        return {"full_name": str(repo.full_name), "memories": [_view(m) for m in rows]}

    async def recall_organization(
        self, organization: str, *, query: str | None = None,
        kind: str | None = None, limit: int = 50,
    ) -> dict[str, Any]:
        if not is_organization_allowed(organization):
            raise UnknownResourceError(f"organization '{organization}' is not accessible")
        rows = await self.memories.list_for_organization(
            organization, kind=kind, query=query, limit=limit
        )
        return {"organization": organization, "memories": [_view(m) for m in rows]}

    async def forget(self, memory_id: UUID) -> bool:
        """Delete a memory after checking the caller may access its owner.

        Never deletes by bare id: an out-of-scope (or unknown) memory reads as
        absent, so callers get the same not-found result as an unknown id.
        """
        memory = await self.memories.get(memory_id)
        if memory is None or not await self._may_access(memory):
            return False
        return await self.memories.delete(memory_id)

    async def _may_access(self, memory: AgentMemory) -> bool:
        if memory.repository_id is not None:
            # Repository resolution passes through the per-org choke point, so an
            # out-of-scope repo reads as absent.
            return await self.repositories.get(memory.repository_id) is not None
        if memory.organization is not None:
            return is_organization_allowed(memory.organization)
        # Unowned memory: only an unrestricted (admin/worker) caller may touch it.
        return is_unrestricted()
