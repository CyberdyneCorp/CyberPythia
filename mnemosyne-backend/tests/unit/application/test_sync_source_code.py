"""Unit tests for the source-code sync step (spec: code-context / repository-sync)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.application.use_cases.github_connections import GitHubConnectionUseCases
from app.application.use_cases.sync_repository import MetricsWriter, SyncRepositoryUseCase
from app.domain.entities.repository import Repository
from app.domain.entities.sync_job import SyncJob
from app.domain.ports.github_port import GitHubFileData, GitHubRepoData
from app.domain.services.code_chunker import HeuristicCodeChunker
from app.domain.value_objects.enums import IndexingMode, RepositoryVisibility, SyncStatus, SyncStep
from app.domain.value_objects.full_name import RepositoryFullName
from tests.unit.application.fakes import (
    FakeCipher,
    FakeConnectionPort,
    FakeDocumentPort,
    FakeFilePort,
    FakeGitHub,
    FakeIssuePort,
    FakeOpenSpecPort,
    FakePullRequestPort,
    FakeRepositoryPort,
    FakeSourceChunkPort,
    FakeStorage,
    FakeSyncJobPort,
    FakeSyncLock,
)
from tests.unit.application.test_sync_repository import FakeEmbeddings, FakeMetricsStore

NOW = datetime(2026, 7, 7, tzinfo=UTC)

SECRET_LINE = 'aws = "AKIAIOSFODNN7EXAMPLE"\nkey=AKIAIOSFODNN7EXAMPLE'


@pytest.fixture
def env():
    github = FakeGitHub()
    github.repos = [
        GitHubRepoData(
            github_id=1, full_name="cyberdyne/a", description="d", visibility="private",
            default_branch="main", primary_language="Python", archived=False, updated_at=NOW,
        )
    ]
    github.tree = [
        GitHubFileData(path="README.md", sha="r", size=20, is_binary=False),
        GitHubFileData(path="src/app.py", sha="c1", size=60, is_binary=False),
        GitHubFileData(path="logo.png", sha="b", size=999, is_binary=True),
        GitHubFileData(path="secrets/creds.py", sha="s", size=30, is_binary=False),
        GitHubFileData(path="src/keys.py", sha="k", size=40, is_binary=False),
        GitHubFileData(path="huge.py", sha="h", size=2_000_000, is_binary=False),
    ]
    github.files = {
        "README.md": "# Demo\n\nHello.",
        "src/app.py": "def dispatch():\n    return 1\n\nclass Backend:\n    pass\n",
        "src/keys.py": SECRET_LINE,
        "huge.py": "x = 1\n",
    }
    connections = FakeConnectionPort()
    connection_uc = GitHubConnectionUseCases(connections, github, FakeCipher())
    repositories = FakeRepositoryPort()
    files = FakeFilePort()
    source_chunks = FakeSourceChunkPort()
    sync_jobs = FakeSyncJobPort()
    embeddings = FakeEmbeddings()
    use_case = SyncRepositoryUseCase(
        repositories=repositories,
        documents=FakeDocumentPort(),
        openspec=FakeOpenSpecPort(),
        issues=FakeIssuePort(),
        pull_requests=FakePullRequestPort(),
        files=files,
        sync_jobs=sync_jobs,
        github=github,
        connection_use_cases=connection_uc,
        sync_lock=FakeSyncLock(),
        storage=FakeStorage(),
        embeddings=embeddings,
        metrics_writer=MetricsWriter(store=FakeMetricsStore()),
        source_chunks=source_chunks,
        code_chunker=HeuristicCodeChunker(),
        source_size_cap=1_000_000,
    )
    return {
        "use_case": use_case, "github": github, "connection_uc": connection_uc,
        "repositories": repositories, "files": files, "source_chunks": source_chunks,
        "sync_jobs": sync_jobs, "embeddings": embeddings,
    }


async def seed(env, mode=IndexingMode.CODE_CONTEXT):
    connection = await env["connection_uc"].connect("ghp_secret_ab12")
    repo = Repository(
        id=uuid4(), connection_id=connection.id, github_id=1,
        full_name=RepositoryFullName("cyberdyne/a"), description=None,
        visibility=RepositoryVisibility.PRIVATE, default_branch="main",
        primary_language=None, archived=False, github_updated_at=None,
        enabled=True, indexing_mode=mode,
    )
    await env["repositories"].save(repo)
    job = SyncJob(id=uuid4(), repository_id=repo.id, mode=mode)
    job.plan()
    await env["sync_jobs"].save(job)
    return repo, job


async def files_by_path(env, repo_id):
    return {f.path: f for f in await env["files"].list_by_repository(repo_id)}


class TestSourceCodeStep:
    async def test_captures_and_chunks_for_code_context(self, env):
        repo, job = await seed(env)
        result = await env["use_case"].run(repo.id, job.id)
        assert result.status is SyncStatus.SUCCEEDED

        by_path = await files_by_path(env, repo.id)
        app = by_path["src/app.py"]
        assert app.content_captured and app.content is not None
        # symbol chunks produced and embedded
        chunks = await env["source_chunks"].list_by_repository(repo.id)
        symbols = {c.symbol_name for c in chunks}
        assert "dispatch" in symbols and "Backend" in symbols
        assert env["embeddings"].code_embedded  # source chunks embedded

    async def test_binary_content_with_null_bytes_is_skipped(self, env):
        # A file the extension check treats as text but whose content is binary
        # (glTF/CAD blob with a NUL byte) must be skipped — a NUL can't be stored
        # in a Postgres text column and would fail the source_code step.
        env["github"].tree.append(
            GitHubFileData(path="assets/scene.model", sha="m", size=50, is_binary=False))
        env["github"].files["assets/scene.model"] = "glTF\x00\x00\x00binary junk"
        repo, job = await seed(env)
        result = await env["use_case"].run(repo.id, job.id)
        assert result.status is SyncStatus.SUCCEEDED  # not failed/degraded
        by_path = await files_by_path(env, repo.id)
        model = by_path["assets/scene.model"]
        assert not model.content_captured and model.content is None

    async def test_skipped_below_code_context(self, env):
        repo, job = await seed(env, mode=IndexingMode.CODE_METADATA)
        result = await env["use_case"].run(repo.id, job.id)
        assert result.status is SyncStatus.SUCCEEDED
        assert SyncStep.SOURCE_CODE not in [s.step for s in result.steps]
        # file tree captured, but no content / chunks
        by_path = await files_by_path(env, repo.id)
        assert not by_path["src/app.py"].content_captured
        assert await env["source_chunks"].list_by_repository(repo.id) == []

    async def test_binary_and_oversize_excluded(self, env):
        repo, job = await seed(env)
        await env["use_case"].run(repo.id, job.id)
        by_path = await files_by_path(env, repo.id)
        assert not by_path["logo.png"].content_captured  # binary
        assert not by_path["huge.py"].content_captured  # over cap (2MB > 1MB)

    async def test_denylisted_path_excluded(self, env):
        repo, job = await seed(env)
        await env["use_case"].run(repo.id, job.id)
        by_path = await files_by_path(env, repo.id)
        # secrets/ is on the default denylist -> not even in the file tree
        assert "secrets/creds.py" not in by_path

    async def test_secret_file_quarantined(self, env):
        repo, job = await seed(env)
        await env["use_case"].run(repo.id, job.id)
        by_path = await files_by_path(env, repo.id)
        keys = by_path["src/keys.py"]
        assert keys.quarantined
        assert keys.content is None and not keys.content_captured
        # no chunks for a quarantined file
        chunks = await env["source_chunks"].list_by_repository(repo.id)
        assert all(c.file_id != keys.id for c in chunks)

    async def test_resync_skips_unchanged_file(self, env):
        repo, job = await seed(env)
        await env["use_case"].run(repo.id, job.id)
        first = len(env["embeddings"].code_embedded)

        job2 = SyncJob(id=uuid4(), repository_id=repo.id, mode=repo.indexing_mode)
        job2.plan()
        await env["sync_jobs"].save(job2)
        await env["use_case"].run(repo.id, job2.id)
        # unchanged content -> no re-embedding
        assert len(env["embeddings"].code_embedded) == first

    async def test_resync_reembeds_changed_file(self, env):
        repo, job = await seed(env)
        await env["use_case"].run(repo.id, job.id)
        first = len(env["embeddings"].code_embedded)

        env["github"].files["src/app.py"] = "def dispatch():\n    return 999\n"
        job2 = SyncJob(id=uuid4(), repository_id=repo.id, mode=repo.indexing_mode)
        job2.plan()
        await env["sync_jobs"].save(job2)
        await env["use_case"].run(repo.id, job2.id)
        assert len(env["embeddings"].code_embedded) > first
