"""End-to-end sync: real Postgres/Redis/MinIO adapters, GitHub mocked with respx."""

from uuid import uuid4

import respx
from cryptography.fernet import Fernet

from app.application.use_cases.github_connections import GitHubConnectionUseCases
from app.application.use_cases.sync_repository import MetricsWriter, SyncRepositoryUseCase
from app.domain.entities.repository import Repository
from app.domain.entities.sync_job import SyncJob
from app.domain.services.code_chunker import HeuristicCodeChunker
from app.domain.value_objects.enums import (
    IndexingMode,
    RepositoryVisibility,
    SyncStatus,
)
from app.domain.value_objects.full_name import RepositoryFullName
from app.infrastructure.github.client import API_BASE, GitHubClient
from app.infrastructure.object_storage.minio_storage import MinioStorageAdapter
from app.infrastructure.persistence.repositories.connections import PostgresConnectionRepository
from app.infrastructure.persistence.repositories.documents import (
    PostgresDocumentRepository,
    PostgresOpenSpecRepository,
)
from app.infrastructure.persistence.repositories.misc import (
    PostgresFileRepository,
    PostgresMetricsRepository,
    PostgresSourceChunkRepository,
    PostgresSyncJobRepository,
)
from app.infrastructure.persistence.repositories.repositories import PostgresRepositoryRepository
from app.infrastructure.persistence.repositories.work_items import (
    PostgresIssueRepository,
    PostgresPullRequestRepository,
)
from app.infrastructure.queue.redis_queue import RedisSyncLock
from app.infrastructure.security.token_encryption import TokenEncryption
from tests.integration.conftest import MINIO_ENDPOINT, REDIS_URL

FULL_NAME = "cyberdyne/matforge"


class NoopEmbeddings:
    async def embed_document(self, document_id, repository_id, chunks):
        return len(chunks)

    async def delete_document(self, document_id):
        pass

    async def search(self, repository_id, query, *, limit=8):
        return []

    async def embed_source_chunks(self, repository_id, chunks):
        return len(chunks)

    async def search_code(self, repository_id, query, *, limit=8):
        return []


def mock_github():
    def b64(content: str) -> dict:
        import base64

        return {"encoding": "base64", "content": base64.b64encode(content.encode()).decode()}

    respx.get(f"{API_BASE}/repos/{FULL_NAME}").respond(
        json={
            "id": 99,
            "full_name": FULL_NAME,
            "description": "MATLAB LLVM compiler",
            "visibility": "private",
            "default_branch": "main",
            "language": "C++",
            "archived": False,
            "updated_at": "2026-07-01T00:00:00Z",
        }
    )
    respx.get(f"{API_BASE}/repos/{FULL_NAME}/git/trees/main").respond(
        json={
            "tree": [
                {"type": "blob", "path": "README.md", "sha": "r1", "size": 20},
                {"type": "blob", "path": "openspec/changes/add-gpu/proposal.md", "sha": "o1", "size": 10},
                {"type": "blob", "path": "src/main.cpp", "sha": "c1", "size": 100},
            ]
        }
    )
    respx.get(f"{API_BASE}/repos/{FULL_NAME}/contents/README.md").respond(
        json=b64("# Matforge\n\nA MATLAB compiler.")
    )
    respx.get(f"{API_BASE}/repos/{FULL_NAME}/contents/openspec/changes/add-gpu/proposal.md").respond(
        json=b64("# Proposal: add-gpu")
    )
    respx.get(f"{API_BASE}/repos/{FULL_NAME}/issues").respond(
        json=[
            {
                "id": 1, "number": 42, "title": "Add OpenCL backend", "state": "closed",
                "user": {"login": "alice"}, "labels": [], "assignees": [], "comments": 0,
                "created_at": "2026-06-01T00:00:00Z", "closed_at": "2026-06-05T00:00:00Z",
            }
        ]
    )
    respx.get(f"{API_BASE}/repos/{FULL_NAME}/pulls").respond(
        json=[
            {
                "id": 2, "number": 61, "title": "Refactor GPU backend", "state": "closed",
                "user": {"login": "bob"}, "created_at": "2026-06-02T00:00:00Z",
                "merged_at": "2026-06-04T00:00:00Z", "closed_at": "2026-06-04T00:00:00Z",
            }
        ]
    )
    respx.get(f"{API_BASE}/repos/{FULL_NAME}/releases").respond(json=[])
    respx.get(f"{API_BASE}/repos/{FULL_NAME}/pulls/61/reviews").respond(
        json=[{"user": {"login": "carol"}, "state": "APPROVED",
               "submitted_at": "2026-06-03T00:00:00Z"}]
    )


@respx.mock
async def test_full_sync_against_real_adapters(session_factory):
    mock_github()
    storage = MinioStorageAdapter(
        endpoint=MINIO_ENDPOINT, access_key="mnemosyne", secret_key="mnemosyne-secret",
        bucket="mnemosyne-test", secure=False,
    )
    cipher = TokenEncryption(Fernet.generate_key().decode())
    github = GitHubClient(storage=storage)
    connections = PostgresConnectionRepository(session_factory)
    connection_uc = GitHubConnectionUseCases(connections, github, cipher)

    from tests.integration.persistence.test_repositories import make_connection

    connection = make_connection()
    connection.encrypted_token = cipher.encrypt("ghp_test_token")
    await connections.save(connection)

    repositories = PostgresRepositoryRepository(session_factory)
    repo = Repository(
        id=uuid4(), connection_id=connection.id, github_id=99,
        full_name=RepositoryFullName(FULL_NAME), description=None,
        visibility=RepositoryVisibility.PRIVATE, default_branch="main",
        primary_language=None, archived=False, github_updated_at=None,
        enabled=True, indexing_mode=IndexingMode.PROJECT_INTELLIGENCE,
    )
    await repositories.save(repo)

    sync_jobs = PostgresSyncJobRepository(session_factory)
    job = SyncJob(id=uuid4(), repository_id=repo.id, mode=repo.indexing_mode)
    job.plan()
    await sync_jobs.save(job)

    documents = PostgresDocumentRepository(session_factory)
    metrics_store = PostgresMetricsRepository(session_factory)
    lock = RedisSyncLock(REDIS_URL, ttl_seconds=60)

    use_case = SyncRepositoryUseCase(
        repositories=repositories,
        documents=documents,
        openspec=PostgresOpenSpecRepository(session_factory),
        issues=PostgresIssueRepository(session_factory),
        pull_requests=PostgresPullRequestRepository(session_factory),
        files=PostgresFileRepository(session_factory),
        sync_jobs=sync_jobs,
        github=github,
        connection_use_cases=connection_uc,
        sync_lock=lock,
        storage=storage,
        embeddings=NoopEmbeddings(),
        metrics_writer=MetricsWriter(store=metrics_store),
        source_chunks=PostgresSourceChunkRepository(session_factory),
        code_chunker=HeuristicCodeChunker(),
    )
    try:
        result = await use_case.run(repo.id, job.id)
    finally:
        await lock.close()
        await github.close()

    assert result.status is SyncStatus.SUCCEEDED

    docs = await documents.list_by_repository(repo.id)
    assert "README.md" in [d.path for d in docs]

    stored_job = await sync_jobs.get(job.id)
    assert stored_job.status is SyncStatus.SUCCEEDED

    metrics = await metrics_store.get(repo.id)
    assert metrics["summary"]["has_readme"] is True
    assert metrics["summary"]["closed_issues"] == 1
    assert metrics["issue_metrics"]["avg_resolution_seconds"] == 4 * 86400

    # raw payloads landed in MinIO before normalization
    raw_issues = await storage.get_json(f"raw/github/repos/{FULL_NAME}/issues.json")
    assert raw_issues[0]["number"] == 42

    updated_repo = await repositories.get(repo.id)
    assert updated_repo.last_synced_at is not None


@respx.mock
async def test_code_context_sync_captures_and_chunks_source(session_factory):
    import base64

    from app.domain.services.code_chunker import HeuristicCodeChunker
    from app.infrastructure.persistence.repositories.misc import PostgresSourceChunkRepository
    from tests.integration.persistence.test_repositories import make_connection

    def b64(content: str) -> dict:
        return {"encoding": "base64", "content": base64.b64encode(content.encode()).decode()}

    respx.get(f"{API_BASE}/repos/{FULL_NAME}").respond(
        json={"id": 99, "full_name": FULL_NAME, "visibility": "private",
              "default_branch": "main", "language": "Python", "archived": False}
    )
    respx.get(f"{API_BASE}/repos/{FULL_NAME}/git/trees/main").respond(
        json={"tree": [
            {"type": "blob", "path": "README.md", "sha": "r", "size": 20},
            {"type": "blob", "path": "src/gpu.py", "sha": "g", "size": 80},
        ]}
    )
    respx.get(f"{API_BASE}/repos/{FULL_NAME}/contents/README.md").respond(json=b64("# Matforge"))
    respx.get(f"{API_BASE}/repos/{FULL_NAME}/contents/src/gpu.py").respond(
        json=b64("def dispatch_kernels(n):\n    return n\n\nclass GpuBackend:\n    pass\n")
    )
    respx.get(f"{API_BASE}/repos/{FULL_NAME}/issues").respond(json=[])
    respx.get(f"{API_BASE}/repos/{FULL_NAME}/pulls").respond(json=[])
    respx.get(f"{API_BASE}/repos/{FULL_NAME}/releases").respond(json=[])

    storage = MinioStorageAdapter(
        endpoint=MINIO_ENDPOINT, access_key="mnemosyne", secret_key="mnemosyne-secret",
        bucket="mnemosyne-test", secure=False,
    )
    cipher = TokenEncryption(Fernet.generate_key().decode())
    github = GitHubClient(storage=storage)
    connections = PostgresConnectionRepository(session_factory)
    connection = make_connection()
    connection.encrypted_token = cipher.encrypt("ghp_test")
    await connections.save(connection)

    repositories = PostgresRepositoryRepository(session_factory)
    repo = Repository(
        id=uuid4(), connection_id=connection.id, github_id=99,
        full_name=RepositoryFullName(FULL_NAME), description=None,
        visibility=RepositoryVisibility.PRIVATE, default_branch="main",
        primary_language=None, archived=False, github_updated_at=None,
        enabled=True, indexing_mode=IndexingMode.CODE_CONTEXT,
    )
    await repositories.save(repo)

    sync_jobs = PostgresSyncJobRepository(session_factory)
    job = SyncJob(id=uuid4(), repository_id=repo.id, mode=repo.indexing_mode)
    job.plan()
    await sync_jobs.save(job)

    files = PostgresFileRepository(session_factory)
    chunks = PostgresSourceChunkRepository(session_factory)
    lock = RedisSyncLock(REDIS_URL, ttl_seconds=60)
    use_case = SyncRepositoryUseCase(
        repositories=repositories,
        documents=PostgresDocumentRepository(session_factory),
        openspec=PostgresOpenSpecRepository(session_factory),
        issues=PostgresIssueRepository(session_factory),
        pull_requests=PostgresPullRequestRepository(session_factory),
        files=files,
        sync_jobs=sync_jobs,
        github=github,
        connection_use_cases=GitHubConnectionUseCases(connections, github, cipher),
        sync_lock=lock,
        storage=storage,
        embeddings=NoopEmbeddings(),
        metrics_writer=MetricsWriter(store=PostgresMetricsRepository(session_factory)),
        source_chunks=chunks,
        code_chunker=HeuristicCodeChunker(),
    )
    try:
        result = await use_case.run(repo.id, job.id)
    finally:
        await lock.close()
        await github.close()

    assert result.status is SyncStatus.SUCCEEDED
    by_path = {f.path: f for f in await files.list_by_repository(repo.id)}
    assert by_path["src/gpu.py"].content_captured
    symbols = {c.symbol_name for c in await chunks.list_by_repository(repo.id)}
    assert "dispatch_kernels" in symbols and "GpuBackend" in symbols
