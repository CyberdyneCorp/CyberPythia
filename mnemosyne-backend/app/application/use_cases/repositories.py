"""Repository discovery, selection, and sync triggering (spec: repository-sync)."""

from uuid import UUID, uuid4

from app.application.errors import (
    ApplicationError,
    SyncAlreadyRunningError,
    UnknownResourceError,
)
from app.application.use_cases.github_connections import GitHubConnectionUseCases
from app.domain.entities.repository import Repository
from app.domain.entities.sync_job import SyncJob
from app.domain.ports.github_port import GitHubPort
from app.domain.ports.infra_ports import QueuePort, SyncLockPort
from app.domain.ports.persistence_ports import (
    ConnectionPort,
    OrganizationPort,
    RepositoryPort,
    SyncJobPort,
)
from app.domain.value_objects.enums import (
    ConnectionKind,
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
        organizations: OrganizationPort | None = None,
        default_org_sync_enabled: bool = True,
    ) -> None:
        self._repositories = repositories
        self._connections = connections
        self._connection_use_cases = connection_use_cases
        self._github = github
        self._sync_jobs = sync_jobs
        self._queue = queue
        self._sync_lock = sync_lock
        self._organizations = organizations
        self._default_org_sync_enabled = default_org_sync_enabled

    async def discover(self, connection_id: UUID) -> list[Repository]:
        """Fetch accessible repositories; persist metadata without content (spec)."""
        connection = await self._connections.get(connection_id)
        if connection is None:
            raise UnknownResourceError(f"connection {connection_id} not found")
        token = await self._connection_use_cases.credential_for(connection_id)
        # App installation tokens are server-to-server: they must enumerate repos
        # via /installation/repositories, not the user-context /user/repos.
        if connection.kind is ConnectionKind.GITHUB_APP:
            discovered = await self._github.list_installation_repositories(token)
        else:
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
        if self._organizations is not None:
            owners = sorted({repo.full_name.owner for repo in repositories})
            await self._organizations.upsert_many(
                owners, default_enabled=self._default_org_sync_enabled
            )
        return await self._repositories.list_all()

    async def list_repositories(
        self, *, enabled_only: bool = False, organization: str | None = None
    ) -> list[Repository]:
        repos = await self._repositories.list_all(enabled_only=enabled_only)
        if organization:
            owner = organization.lower()
            repos = [r for r in repos if r.full_name.owner.lower() == owner]
        return repos

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

    async def bulk_update_selection(
        self,
        repository_ids: list[UUID] | None = None,
        *,
        enabled: bool,
        mode: IndexingMode | None = None,
        organization: str | None = None,
    ) -> int:
        """Set enabled (+ optional mode) for many repositories in one batched write.

        Targets either an explicit id list or every repository in ``organization``.
        Unknown ids are ignored. Returns the number of repositories updated.
        """
        all_repos = await self._repositories.list_all()
        if organization:
            owner = organization.lower()
            repos = [r for r in all_repos if r.full_name.owner.lower() == owner]
        else:
            wanted = set(repository_ids or [])
            repos = [r for r in all_repos if r.id in wanted]
        for repo in repos:
            if enabled:
                repo.enable(mode or repo.indexing_mode)
            else:
                repo.disable()
        if repos:
            await self._repositories.save_many(repos)
        return len(repos)

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

    async def sync_all(
        self, *, triggered_by: str, organization: str | None = None,
        stagger_seconds: float = 0.0,
    ) -> dict[str, int]:
        """Enqueue a sync for every enabled repository (optionally one org).

        Reuses the per-repo enqueue path: an already-running sync is skipped and a
        single failure doesn't stop the rest. Returns enqueued/skipped counts.
        """
        from app.application.use_cases.scheduled_sync import least_recently_synced_first

        repos = await self._repositories.list_all(enabled_only=True)
        if organization:
            owner = organization.lower()
            repos = [r for r in repos if r.full_name.owner.lower() == owner]
        repos = least_recently_synced_first(repos)  # oldest first under budget pressure
        enqueued = skipped = 0
        for repo in repos:
            try:
                await self.trigger_sync(
                    repo.id, triggered_by=triggered_by,
                    defer_seconds=enqueued * stagger_seconds,
                )
                enqueued += 1
            except SyncAlreadyRunningError:
                skipped += 1
            except ApplicationError:
                skipped += 1
        return {"enqueued": enqueued, "skipped": skipped}

    async def sync_status(self, repository_id: UUID) -> SyncJob | None:
        await self.get(repository_id)
        return await self._sync_jobs.get_latest(repository_id)
