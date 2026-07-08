"""Scheduled discovery + auto-enable of newly-seen repositories (spec: repository-sync).

Runs in the worker ahead of the daily full sync. For each connection it re-runs the
existing discovery (which preserves each repo's enabled state), then enables only
repositories whose GitHub id was **not present before** this run and that are not
archived — so a manually disabled repo is never re-enabled.
"""

import logging
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.domain.entities.github_connection import GitHubConnection
from app.domain.entities.repository import Repository
from app.domain.value_objects.enums import IndexingMode

logger = logging.getLogger(__name__)


class _Repositories(Protocol):
    async def list_all(self, *, enabled_only: bool = False) -> list[Repository]: ...


class _Connections(Protocol):
    async def list_all(self) -> list[GitHubConnection]: ...


class _RepoUseCases(Protocol):
    async def discover(self, connection_id: UUID) -> list[Repository]: ...

    async def update_selection(
        self, repository_id: UUID, *, enabled: bool, mode: IndexingMode | None = None
    ) -> Repository: ...


class _Organizations(Protocol):
    async def disabled_logins(self) -> set[str]: ...


@dataclass(frozen=True, slots=True)
class ScheduledDiscoverySummary:
    discovered: int
    newly_enabled: int
    skipped_archived: int


class ScheduledDiscoveryService:
    def __init__(
        self,
        repositories: _Repositories,
        connections: _Connections,
        repository_use_cases: _RepoUseCases,
        *,
        auto_enable: bool,
        mode: IndexingMode,
        include_archived: bool,
        organizations: "_Organizations | None" = None,
    ) -> None:
        self._repositories = repositories
        self._connections = connections
        self._use_cases = repository_use_cases
        self._auto_enable = auto_enable
        self._mode = mode
        self._include_archived = include_archived
        self._organizations = organizations

    async def run(self) -> ScheduledDiscoverySummary:
        before = {r.github_id for r in await self._repositories.list_all()}
        for connection in await self._connections.list_all():
            try:
                await self._use_cases.discover(connection.id)
            except Exception:
                logger.exception("scheduled discovery: failed for connection %s", connection.id)

        after = await self._repositories.list_all()
        disabled = (
            await self._organizations.disabled_logins() if self._organizations else set()
        )
        newly_enabled = skipped_archived = 0
        if self._auto_enable:
            for repo in after:
                if repo.github_id in before:
                    continue  # pre-existing -> never touch its enabled state
                if repo.archived and not self._include_archived:
                    skipped_archived += 1
                    continue
                if repo.full_name.owner in disabled:
                    continue  # organization sync disabled -> do not auto-enable
                await self._use_cases.update_selection(repo.id, enabled=True, mode=self._mode)
                newly_enabled += 1

        summary = ScheduledDiscoverySummary(
            discovered=len(after),
            newly_enabled=newly_enabled,
            skipped_archived=skipped_archived,
        )
        logger.info(
            "scheduled discovery: %d repos known, %d newly enabled, %d archived skipped",
            summary.discovered,
            summary.newly_enabled,
            summary.skipped_archived,
        )
        return summary
