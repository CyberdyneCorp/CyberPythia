"""Unit tests for discovery, selection, and sync triggering (spec: repository-sync)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.application.errors import SyncAlreadyRunningError, UnknownResourceError
from app.application.use_cases.github_connections import GitHubConnectionUseCases
from app.application.use_cases.repositories import RepositoryUseCases
from app.domain.ports.github_port import GitHubRepoData
from app.domain.value_objects.enums import IndexingMode, SyncStatus
from tests.unit.application.fakes import (
    FakeCipher,
    FakeConnectionPort,
    FakeGitHub,
    FakeQueue,
    FakeRepositoryPort,
    FakeSyncJobPort,
    FakeSyncLock,
)

NOW = datetime(2026, 7, 7, tzinfo=UTC)


def repo_data(github_id, full_name):
    return GitHubRepoData(
        github_id=github_id,
        full_name=full_name,
        description="d",
        visibility="private",
        default_branch="main",
        primary_language="Python",
        archived=False,
        updated_at=NOW,
    )


@pytest.fixture
def env():
    github = FakeGitHub()
    github.repos = [repo_data(1, "cyberdyne/a"), repo_data(2, "cyberdyne/b")]
    connections = FakeConnectionPort()
    connection_uc = GitHubConnectionUseCases(connections, github, FakeCipher())
    repositories = FakeRepositoryPort()
    sync_jobs = FakeSyncJobPort()
    queue = FakeQueue()
    lock = FakeSyncLock()
    use_cases = RepositoryUseCases(
        repositories, connections, connection_uc, github, sync_jobs, queue, lock
    )
    return use_cases, github, connection_uc, queue, lock, sync_jobs


async def connect(connection_uc):
    return await connection_uc.connect("ghp_secret_ab12")


class TestDiscovery:
    async def test_discover_persists_metadata_without_content(self, env):
        use_cases, _, connection_uc, queue, *_ = env
        connection = await connect(connection_uc)
        repos = await use_cases.discover(connection.id)
        assert [str(r.full_name) for r in repos] == ["cyberdyne/a", "cyberdyne/b"]
        assert all(not r.enabled for r in repos)  # nothing auto-indexed (spec)
        assert queue.jobs == []

    async def test_list_repositories_filters_by_organization(self, env):
        use_cases, github, connection_uc, *_ = env
        github.repos = [repo_data(1, "cyberdyne/a"), repo_data(2, "aminitech/b")]
        connection = await connect(connection_uc)
        await use_cases.discover(connection.id)
        cyber = await use_cases.list_repositories(organization="CyberDyne")  # case-insensitive
        assert [str(r.full_name) for r in cyber] == ["cyberdyne/a"]
        allrepos = await use_cases.list_repositories()
        assert len(allrepos) == 2

    async def test_discover_upserts_organizations(self):
        from tests.unit.application.fakes import FakeOrganizationPort

        github = FakeGitHub()
        github.repos = [
            repo_data(1, "cyberdyne/a"), repo_data(2, "aminitech/b"), repo_data(3, "cyberdyne/c")
        ]
        connections = FakeConnectionPort()
        connection_uc = GitHubConnectionUseCases(connections, github, FakeCipher())
        orgs = FakeOrganizationPort()
        use_cases = RepositoryUseCases(
            FakeRepositoryPort(), connections, connection_uc, github,
            FakeSyncJobPort(), FakeQueue(), FakeSyncLock(), organizations=orgs,
        )
        connection = await connect(connection_uc)
        await use_cases.discover(connection.id)
        assert set(orgs.orgs) == {"cyberdyne", "aminitech"}  # distinct owners upserted
        assert all(orgs.orgs.values())  # default enabled

    async def test_rediscovery_preserves_selection(self, env):
        use_cases, _, connection_uc, *_ = env
        connection = await connect(connection_uc)
        repos = await use_cases.discover(connection.id)
        await use_cases.update_selection(
            repos[0].id, enabled=True, mode=IndexingMode.CODE_METADATA
        )
        repos_again = await use_cases.discover(connection.id)
        target = next(r for r in repos_again if str(r.full_name) == "cyberdyne/a")
        assert target.enabled
        assert target.indexing_mode is IndexingMode.CODE_METADATA

    async def test_discover_unknown_connection(self, env):
        use_cases, *_ = env
        with pytest.raises(UnknownResourceError):
            await use_cases.discover(uuid4())

    async def test_app_connection_discovers_via_installation_path(self):
        """Regression: App installation tokens 403 on /user/repos, so discovery
        must enumerate via /installation/repositories."""
        from tests.unit.application.fakes import FakeGitHubAppAuth

        github = FakeGitHub()
        github.repos = []  # user-context path must NOT be used for an App
        github.installation_repos = [repo_data(1, "cyberdyne/a"), repo_data(2, "cyberdyne/b")]
        connections = FakeConnectionPort()
        connection_uc = GitHubConnectionUseCases(
            connections, github, FakeCipher(), app_auth=FakeGitHubAppAuth()
        )
        use_cases = RepositoryUseCases(
            FakeRepositoryPort(), connections, connection_uc, github,
            FakeSyncJobPort(), FakeQueue(), FakeSyncLock(),
        )
        view = await connection_uc.connect_app("app1", "inst1", "pem", "secret")
        repos = await use_cases.discover(view.id)
        assert [str(r.full_name) for r in repos] == ["cyberdyne/a", "cyberdyne/b"]


class TestSelection:
    async def test_enable_disable(self, env):
        use_cases, _, connection_uc, *_ = env
        connection = await connect(connection_uc)
        repos = await use_cases.discover(connection.id)
        enabled = await use_cases.update_selection(
            repos[0].id, enabled=True, mode=IndexingMode.PROJECT_INTELLIGENCE
        )
        assert enabled.enabled
        disabled = await use_cases.update_selection(repos[0].id, enabled=False)
        assert not disabled.enabled

    async def test_list_enabled_only(self, env):
        use_cases, _, connection_uc, *_ = env
        connection = await connect(connection_uc)
        repos = await use_cases.discover(connection.id)
        await use_cases.update_selection(repos[1].id, enabled=True)
        only = await use_cases.list_repositories(enabled_only=True)
        assert [str(r.full_name) for r in only] == ["cyberdyne/b"]


class TestTriggerSync:
    async def make_enabled_repo(self, env):
        use_cases, _, connection_uc, *_ = env
        connection = await connect(connection_uc)
        repos = await use_cases.discover(connection.id)
        await use_cases.update_selection(
            repos[0].id, enabled=True, mode=IndexingMode.PROJECT_INTELLIGENCE
        )
        return repos[0]

    async def test_trigger_enqueues_planned_job(self, env):
        use_cases, _, _, queue, _, _sync_jobs = env
        repo = await self.make_enabled_repo(env)
        job = await use_cases.trigger_sync(repo.id, triggered_by="admin-1")
        assert job.status is SyncStatus.PENDING
        assert job.triggered_by == "admin-1"
        assert len(job.steps) > 0
        assert queue.jobs == [
            ("sync_repository", {"repository_id": str(repo.id), "job_id": str(job.id)}, 0.0)
        ]

    async def test_trigger_on_disabled_repo_rejected(self, env):
        use_cases, _, connection_uc, *_ = env
        connection = await connect(connection_uc)
        repos = await use_cases.discover(connection.id)
        with pytest.raises(UnknownResourceError):
            await use_cases.trigger_sync(repos[0].id, triggered_by="admin-1")

    async def test_conflict_when_lock_held(self, env):
        use_cases, _, _, _, lock, _ = env
        repo = await self.make_enabled_repo(env)
        await lock.acquire(repo.id)
        with pytest.raises(SyncAlreadyRunningError):
            await use_cases.trigger_sync(repo.id, triggered_by="admin-1")

    async def test_conflict_when_job_pending(self, env):
        use_cases, *_ = env
        repo = await self.make_enabled_repo(env)
        await use_cases.trigger_sync(repo.id, triggered_by="admin-1")
        with pytest.raises(SyncAlreadyRunningError):
            await use_cases.trigger_sync(repo.id, triggered_by="admin-1")

    async def test_sync_status_returns_latest(self, env):
        use_cases, *_ = env
        repo = await self.make_enabled_repo(env)
        job = await use_cases.trigger_sync(repo.id, triggered_by="admin-1")
        assert (await use_cases.sync_status(repo.id)).id == job.id


class TestBulkSelection:
    async def test_bulk_enable_and_disable(self, env):
        use_cases, github, connection_uc, *_ = env
        github.repos = [repo_data(1, "cyberdyne/a"), repo_data(2, "cyberdyne/b")]
        connection = await connect(connection_uc)
        repos = await use_cases.discover(connection.id)
        ids = [r.id for r in repos]
        from app.domain.value_objects.enums import IndexingMode
        n = await use_cases.bulk_update_selection(
            ids, enabled=True, mode=IndexingMode.CODE_METADATA
        )
        assert n == 2
        after = await use_cases.list_repositories(enabled_only=True)
        assert {str(r.full_name) for r in after} == {"cyberdyne/a", "cyberdyne/b"}
        assert all(r.indexing_mode is IndexingMode.CODE_METADATA for r in after)
        # disable all
        assert await use_cases.bulk_update_selection(ids, enabled=False) == 2
        assert await use_cases.list_repositories(enabled_only=True) == []

    async def test_bulk_ignores_unknown_ids(self, env):
        from uuid import uuid4
        use_cases, *_ = env
        assert await use_cases.bulk_update_selection([uuid4()], enabled=True) == 0

    async def test_bulk_by_organization(self, env):
        use_cases, github, connection_uc, *_ = env
        github.repos = [repo_data(1, "cyberdyne/a"), repo_data(2, "aminitech/b"),
                        repo_data(3, "cyberdyne/c")]
        connection = await connect(connection_uc)
        await use_cases.discover(connection.id)
        n = await use_cases.bulk_update_selection(enabled=True, organization="CyberDyne")
        assert n == 2  # case-insensitive, only cyberdyne/*
        enabled = {str(r.full_name) for r in await use_cases.list_repositories(enabled_only=True)}
        assert enabled == {"cyberdyne/a", "cyberdyne/c"}
