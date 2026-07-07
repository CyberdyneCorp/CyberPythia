"""Repository discovery, selection, and sync triggering (spec: repository-sync)."""

from uuid import UUID, uuid4

from app.application.errors import SyncAlreadyRunningError, UnknownResourceError
from app.application.use_cases.github_connections import GitHubConnectionUseCases
from app.domain.entities.repository import Repository
from app.domain.entities.sync_job import SyncJob
from app.domain.ports.github_port import GitHubPort
from app.domain.ports.infra_ports import QueuePort, SyncLockPort
from app.domain.ports.persistence_ports import ConnectionPort, RepositoryPort, SyncJobPort
from app.domain.value_objects.enums import (
    IndexingMode,
    RepositoryVisibility,
    SyncStatus,
)
from app.domain.value_objects.full_name import RepositoryFullName


class RepositoryUseCases:
    def __init__(
        self,
        repositories: RepositoryPort,
        connections: ConnectionPort,
        connection_use_cases: GitHubConnectionUseCases,
        github: GitHubPort,
        sync_jobs: SyncJobPort,
        queue: QueuePort,
        sync_lock: SyncLockPort,
    ) -> None:
        self._repositories = repositories
        self._connections = connections
        self._connection_use_cases = connection_use_cases
        self._github = github
        self._sync_jobs = sync_jobs
        self._queue = queue
        self._sync_lock = sync_lock

    async def discover(self, connection_id: UUID) -> list[Repository]:
        """Fetch accessible repositories; persist metadata without content (spec)."""
        connection = await self._connections.get(connection_id)
        if connection is None:
            raise UnknownResourceError(f"connection {connection_id} not found")
        token = await self._connection_use_cases.credential_for(connection_id)
        discovered = await self._github.list_repositories(token)
        repositories = [
            Repository(
                id=uuid4(),
                connection_id=connection_id,
                github_id=r.github_id,
                full_name=RepositoryFullName(r.full_name),
                description=r.description,
                visibility=RepositoryVisibility(r.visibility),
                default_branch=r.default_branch,
                primary_language=r.primary_language,
                archived=r.archived,
                github_updated_at=r.updated_at,
            )
            for r in discovered
        ]
        # save_many reconciles ids on github_id so selection state is preserved
        existing = {r.github_id: r for r in await self._repositories.list_all()}
        for repo in repositories:
            if (prior := existing.get(repo.github_id)) is not None:
                repo.enabled = prior.enabled
                repo.indexing_mode = prior.indexing_mode
                repo.last_synced_at = prior.last_synced_at
        await self._repositories.save_many(repositories)
        return await self._repositories.list_all()

    async def list_repositories(self, *, enabled_only: bool = False) -> list[Repository]:
        return await self._repositories.list_all(enabled_only=enabled_only)

    async def get(self, repository_id: UUID) -> Repository:
        repository = await self._repositories.get(repository_id)
        if repository is None:
            raise UnknownResourceError(f"repository {repository_id} not found")
        return repository

    async def get_by_full_name(self, full_name: str) -> Repository | None:
        return await self._repositories.get_by_full_name(full_name)

    async def update_selection(
        self, repository_id: UUID, *, enabled: bool, mode: IndexingMode | None = None
    ) -> Repository:
        repository = await self.get(repository_id)
        if enabled:
            repository.enable(mode or repository.indexing_mode)
        else:
            repository.disable()
        await self._repositories.save(repository)
        return repository

    async def trigger_sync(
        self, repository_id: UUID, *, triggered_by: str, defer_seconds: float = 0.0
    ) -> SyncJob:
        """Enqueue a sync unless one is already running (spec: sync conflict)."""
        repository = await self.get(repository_id)
        if not repository.enabled:
            raise UnknownResourceError(
                f"repository {repository.full_name} is not enabled for indexing"
            )
        if await self._sync_lock.is_locked(repository_id):
            raise SyncAlreadyRunningError(str(repository.full_name))
        latest = await self._sync_jobs.get_latest(repository_id)
        if latest is not None and latest.status in (SyncStatus.PENDING, SyncStatus.RUNNING):
            raise SyncAlreadyRunningError(str(repository.full_name))

        job = SyncJob(
            id=uuid4(),
            repository_id=repository_id,
            mode=repository.indexing_mode,
            triggered_by=triggered_by,
        )
        job.plan()
        await self._sync_jobs.save(job)
        await self._queue.enqueue(
            "sync_repository",
            {"repository_id": str(repository_id), "job_id": str(job.id)},
            defer_seconds=defer_seconds,
        )
        return job

    async def sync_status(self, repository_id: UUID) -> SyncJob | None:
        await self.get(repository_id)
        return await self._sync_jobs.get_latest(repository_id)
