from uuid import uuid4

from app.application.use_cases.scheduled_discovery import ScheduledDiscoveryService
from app.domain.entities.repository import Repository
from app.domain.value_objects.enums import IndexingMode, RepositoryVisibility
from app.domain.value_objects.full_name import RepositoryFullName
from tests.unit.application.fakes import FakeRepositoryPort


def repo(gh_id, name, *, enabled=False, archived=False) -> Repository:
    return Repository(
        id=uuid4(), connection_id=uuid4(), github_id=gh_id,
        full_name=RepositoryFullName(name), description="d",
        visibility=RepositoryVisibility.PRIVATE, default_branch="main",
        primary_language="Python", archived=archived, github_updated_at=None,
        enabled=enabled, indexing_mode=IndexingMode.DOCS_ONLY,
    )


class FakeConnections:
    def __init__(self, ids):
        self._ids = ids

    async def list_all(self):
        return [type("C", (), {"id": i})() for i in self._ids]


class FakeRepoUseCases:
    """Wraps a FakeRepositoryPort; discover() injects a preset batch of repos."""

    def __init__(self, repos: FakeRepositoryPort, discover_batches: dict):
        self._repos = repos
        self._batches = discover_batches
        self.enabled_calls: list = []

    async def discover(self, connection_id):
        batch = self._batches.get(connection_id, [])
        await self._repos.save_many(batch)
        return batch

    async def update_selection(self, repository_id, *, enabled, mode=None):
        r = await self._repos.get(repository_id)
        r.enabled = enabled
        if mode:
            r.indexing_mode = mode
        await self._repos.save(r)
        self.enabled_calls.append((repository_id, enabled, mode))
        return r


PI = IndexingMode.PROJECT_INTELLIGENCE


async def test_new_repo_is_enabled() -> None:
    repos = FakeRepositoryPort()
    await repos.save(repo(1, "cyberdyne/existing", enabled=True))  # pre-existing
    cid = uuid4()
    new = repo(2, "cyberdyne/brand-new")
    uc = FakeRepoUseCases(repos, {cid: [new]})
    svc = ScheduledDiscoveryService(
        repos, FakeConnections([cid]), uc, auto_enable=True, mode=PI, include_archived=False
    )
    summary = await svc.run()
    assert summary.newly_enabled == 1
    stored = await repos.get_by_full_name("cyberdyne/brand-new")
    assert stored.enabled is True and stored.indexing_mode is PI


async def test_preexisting_disabled_is_not_reenabled() -> None:
    repos = FakeRepositoryPort()
    await repos.save(repo(1, "cyberdyne/disabled-by-admin", enabled=False))
    cid = uuid4()
    # discovery re-sees the same repo (github_id 1) -> must stay disabled
    uc = FakeRepoUseCases(repos, {cid: [repo(1, "cyberdyne/disabled-by-admin", enabled=False)]})
    svc = ScheduledDiscoveryService(
        repos, FakeConnections([cid]), uc, auto_enable=True, mode=PI, include_archived=False
    )
    summary = await svc.run()
    assert summary.newly_enabled == 0
    assert uc.enabled_calls == []
    stored = await repos.get_by_full_name("cyberdyne/disabled-by-admin")
    assert stored.enabled is False


async def test_archived_new_repo_skipped() -> None:
    repos = FakeRepositoryPort()
    cid = uuid4()
    uc = FakeRepoUseCases(repos, {cid: [repo(9, "cyberdyne/archived", archived=True)]})
    svc = ScheduledDiscoveryService(
        repos, FakeConnections([cid]), uc, auto_enable=True, mode=PI, include_archived=False
    )
    summary = await svc.run()
    assert summary.newly_enabled == 0 and summary.skipped_archived == 1


async def test_auto_enable_off_no_ops() -> None:
    repos = FakeRepositoryPort()
    cid = uuid4()
    uc = FakeRepoUseCases(repos, {cid: [repo(2, "cyberdyne/new")]})
    svc = ScheduledDiscoveryService(
        repos, FakeConnections([cid]), uc, auto_enable=False, mode=PI, include_archived=False
    )
    summary = await svc.run()
    assert summary.newly_enabled == 0
    assert uc.enabled_calls == []


async def test_disabled_org_new_repo_not_enabled() -> None:
    from tests.unit.application.fakes import FakeOrganizationPort

    repos = FakeRepositoryPort()
    cid = uuid4()
    # two new repos: one in a disabled org, one in an enabled org
    uc = FakeRepoUseCases(
        repos, {cid: [repo(2, "aminitech/new"), repo(3, "cyberdyne/new")]}
    )
    orgs = FakeOrganizationPort()
    await orgs.upsert_many(["aminitech", "cyberdyne"], default_enabled=True)
    await orgs.set_enabled("aminitech", enabled=False)
    svc = ScheduledDiscoveryService(
        repos, FakeConnections([cid]), uc, auto_enable=True, mode=PI,
        include_archived=False, organizations=orgs,
    )
    summary = await svc.run()
    assert summary.newly_enabled == 1  # only cyberdyne/new
    assert (await repos.get_by_full_name("aminitech/new")).enabled is False
    assert (await repos.get_by_full_name("cyberdyne/new")).enabled is True


async def test_connection_error_does_not_abort() -> None:
    repos = FakeRepositoryPort()
    good = uuid4()

    class PartlyFailing(FakeRepoUseCases):
        async def discover(self, connection_id):
            if connection_id != good:
                raise RuntimeError("connection unreachable")
            return await super().discover(connection_id)

    uc = PartlyFailing(repos, {good: [repo(2, "cyberdyne/new")]})
    svc = ScheduledDiscoveryService(
        repos, FakeConnections([uuid4(), good]), uc,
        auto_enable=True, mode=PI, include_archived=False,
    )
    summary = await svc.run()
    assert summary.newly_enabled == 1  # good connection still processed
