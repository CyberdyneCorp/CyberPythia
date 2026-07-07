"""Interface tests for the REST API (spec: rest-api). Fakes behind a real app."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.application.audit import AuditService
from app.application.use_cases.context import ContextUseCases
from app.application.use_cases.github_connections import GitHubConnectionUseCases
from app.application.use_cases.repositories import RepositoryUseCases
from app.domain.entities.document import Document
from app.domain.entities.issue import Issue
from app.domain.entities.repository import Repository
from app.domain.ports.github_port import GitHubRepoData
from app.domain.ports.infra_ports import ChunkMatch
from app.domain.value_objects.enums import (
    DocumentType,
    IndexingMode,
    IssueState,
    RepositoryVisibility,
)
from app.domain.value_objects.full_name import RepositoryFullName
from app.main import create_app
from tests.unit.application.fakes import (
    FakeCipher,
    FakeConnectionPort,
    FakeDocumentPort,
    FakeFilePort,
    FakeGitHub,
    FakeIssuePort,
    FakeOpenSpecPort,
    FakePullRequestPort,
    FakeQueue,
    FakeRepositoryPort,
    FakeStorage,
    FakeSyncJobPort,
    FakeSyncLock,
)
from tests.unit.interfaces.conftest import FakeAuditPort, FakeAuthPort

NOW = datetime(2026, 7, 7, tzinfo=UTC)


class FakeSearchEmbeddings:
    def __init__(self):
        self.matches = []

    async def embed_document(self, document_id, repository_id, chunks):
        return len(chunks)

    async def delete_document(self, document_id):
        pass

    async def search(self, repository_id, query, *, limit=8):
        return self.matches[:limit]


class FakeContextPackPort:
    def __init__(self):
        self.saved = []

    async def save(self, pack):
        self.saved.append(pack)

    async def find_cached(self, repository_id, query, mode, sync_timestamp):
        return None


class FakeMetricsStore:
    def __init__(self):
        self.data = {}

    async def get(self, repository_id):
        return self.data.get(repository_id)

    async def save(self, repository_id, **kw):
        self.data[repository_id] = kw


class FakeAnswerer:
    async def answer(self, question, context_blocks):
        return "Grounded answer [README.md]."


class FakeSessionFactory:
    pass


def build_fake_container():
    github = FakeGitHub()
    github.repos = [
        GitHubRepoData(
            github_id=1, full_name="cyberdyne/a", description="d", visibility="private",
            default_branch="main", primary_language="Python", archived=False, updated_at=NOW,
        )
    ]
    connections = FakeConnectionPort()
    cipher = FakeCipher()
    connection_uc = GitHubConnectionUseCases(connections, github, cipher)
    repositories = FakeRepositoryPort()
    documents = FakeDocumentPort()
    openspec = FakeOpenSpecPort()
    issues = FakeIssuePort()
    prs = FakePullRequestPort()
    files = FakeFilePort()
    sync_jobs = FakeSyncJobPort()
    queue = FakeQueue()
    lock = FakeSyncLock()
    embeddings = FakeSearchEmbeddings()
    metrics_store = FakeMetricsStore()
    audit_port = FakeAuditPort()

    repo_uc = RepositoryUseCases(
        repositories, connections, connection_uc, github, sync_jobs, queue, lock
    )
    context_uc = ContextUseCases(
        repositories=repositories,
        documents=documents,
        openspec=openspec,
        issues=issues,
        pull_requests=prs,
        files=files,
        context_packs=FakeContextPackPort(),
        embeddings=embeddings,
        answerer=FakeAnswerer(),
        metrics_store=metrics_store,
    )
    return SimpleNamespace(
        settings=None,
        session_factory=FakeSessionFactory(),
        auth_port=FakeAuthPort(),
        audit_service=AuditService(audit_port),
        audit_port=audit_port,
        github=github,
        queue=queue,
        sync_lock=lock,
        connections=connections,
        repositories=repositories,
        documents=documents,
        openspec=openspec,
        issues=issues,
        pull_requests=prs,
        files=files,
        sync_jobs=sync_jobs,
        metrics_store=metrics_store,
        storage=FakeStorage(),
        embeddings=embeddings,
        connection_use_cases=connection_uc,
        repository_use_cases=repo_uc,
        context_use_cases=context_uc,
    )


@pytest.fixture
def container():
    return build_fake_container()


@pytest.fixture
def client(container):
    app = create_app(container)
    app.state.auth_port = container.auth_port  # fake token map
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def admin(token="admin-token"):
    return {"Authorization": f"Bearer {token}"}


def user():
    return {"Authorization": "Bearer user-token"}


async def seed_repo(container, *, synced=True, mode=IndexingMode.PROJECT_INTELLIGENCE):
    repo = Repository(
        id=uuid4(), connection_id=uuid4(), github_id=1,
        full_name=RepositoryFullName("cyberdyne/a"), description="d",
        visibility=RepositoryVisibility.PRIVATE, default_branch="main",
        primary_language="Python", archived=False, github_updated_at=NOW,
        enabled=True, indexing_mode=mode, last_synced_at=NOW if synced else None,
    )
    await container.repositories.save(repo)
    return repo


class TestGitHubEndpoints:
    async def test_connect_created(self, client, container):
        async with client as c:
            response = await c.post(
                "/api/v1/github/connect", json={"token": "ghp_secret_ab12"}, headers=admin()
            )
        assert response.status_code == 201
        body = response.json()
        assert body["owner"] == "cyberdyne"
        assert body["token_hint"] == "ab12"
        assert "ghp_secret" not in response.text  # credential never echoed
        # audit written
        assert any(r.operation == "github.connect" for r in container.audit_port.records)

    async def test_connect_requires_admin(self, client):
        async with client as c:
            response = await c.post(
                "/api/v1/github/connect", json={"token": "ghp_secret_ab12"}, headers=user()
            )
        assert response.status_code == 403

    async def test_connect_invalid_credential_400(self, client, container):
        container.github.auth_fails = True
        async with client as c:
            response = await c.post(
                "/api/v1/github/connect", json={"token": "ghp_bad_bad1"}, headers=admin()
            )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "invalid_credential"

    async def test_test_and_delete_connection(self, client, container):
        async with client as c:
            created = await c.post(
                "/api/v1/github/connect", json={"token": "ghp_secret_ab12"}, headers=admin()
            )
            cid = created.json()["id"]
            tested = await c.post(f"/api/v1/github/connections/{cid}/test", headers=admin())
            assert tested.json()["ok"] is True
            deleted = await c.delete(f"/api/v1/github/connections/{cid}", headers=admin())
            assert deleted.status_code == 204
            missing = await c.post(f"/api/v1/github/connections/{cid}/test", headers=admin())
            assert missing.status_code == 404


class TestRepositoryEndpoints:
    async def test_list_requires_entitlement(self, client):
        async with client as c:
            assert (await c.get("/api/v1/repos")).status_code == 401
            denied = await c.get(
                "/api/v1/repos", headers={"Authorization": "Bearer unentitled-token"}
            )
            assert denied.status_code == 403

    async def test_discover_then_list_paginated(self, client, container):
        async with client as c:
            connected = await c.post(
                "/api/v1/github/connect", json={"token": "ghp_secret_ab12"}, headers=admin()
            )
            cid = connected.json()["id"]
            discovered = await c.post(f"/api/v1/repos/discover/{cid}", headers=admin())
            assert discovered.status_code == 200
            listing = await c.get("/api/v1/repos?page=1&page_size=1", headers=user())
        body = listing.json()
        assert body["items"][0]["full_name"] == "cyberdyne/a"
        assert body["next_page"] is None

    async def test_selection_and_sync_flow(self, client, container):
        repo = await seed_repo(container, synced=False)
        async with client as c:
            patched = await c.patch(
                f"/api/v1/repos/{repo.id}",
                json={"enabled": True, "indexing_mode": "code_metadata"},
                headers=admin(),
            )
            assert patched.json()["indexing_mode"] == "code_metadata"

            synced = await c.post(f"/api/v1/repos/{repo.id}/sync", headers=admin())
            assert synced.status_code == 202
            assert container.queue.jobs  # enqueued

            conflict = await c.post(f"/api/v1/repos/{repo.id}/sync", headers=admin())
            assert conflict.status_code == 409
            assert conflict.json()["error"]["code"] == "sync_already_running"

            status = await c.get(f"/api/v1/repos/{repo.id}/sync-status", headers=user())
            assert status.json()["status"] == "pending"

    async def test_sync_requires_admin(self, client, container):
        repo = await seed_repo(container)
        async with client as c:
            response = await c.post(f"/api/v1/repos/{repo.id}/sync", headers=user())
        assert response.status_code == 403

    async def test_unknown_repo_404(self, client):
        async with client as c:
            response = await c.get(f"/api/v1/repos/{uuid4()}/summary", headers=user())
        assert response.status_code == 404


class TestContentEndpoints:
    async def test_docs_listing_and_detail(self, client, container):
        repo = await seed_repo(container)
        doc = Document(
            id=uuid4(), repository_id=repo.id, path="README.md", type=DocumentType.README,
            title="README", content="# hello", content_hash="h", last_commit_sha=None,
            captured_at=NOW,
        )
        await container.documents.save(doc)
        async with client as c:
            listing = await c.get(f"/api/v1/repos/{repo.id}/docs", headers=user())
            assert listing.json()["items"][0]["path"] == "README.md"
            detail = await c.get(f"/api/v1/repos/{repo.id}/docs/{doc.id}", headers=user())
            assert detail.json()["content"] == "# hello"
            missing = await c.get(f"/api/v1/repos/{repo.id}/docs/{uuid4()}", headers=user())
            assert missing.status_code == 404

    async def test_issue_filters(self, client, container):
        repo = await seed_repo(container)
        await container.issues.save_many(
            [
                Issue(
                    id=uuid4(), repository_id=repo.id, github_issue_id=n, number=n,
                    title=f"i{n}", body=None,
                    state=IssueState.OPEN if n == 1 else IssueState.CLOSED,
                    author="alice", labels=["bug"] if n == 1 else [],
                    created_at=NOW, closed_at=None if n == 1 else NOW,
                )
                for n in (1, 2)
            ]
        )
        async with client as c:
            open_only = await c.get(f"/api/v1/repos/{repo.id}/issues?state=open", headers=user())
            assert [i["number"] for i in open_only.json()["items"]] == [1]
            by_label = await c.get(f"/api/v1/repos/{repo.id}/issues?label=bug", headers=user())
            assert [i["number"] for i in by_label.json()["items"]] == [1]
            bad_state = await c.get(f"/api/v1/repos/{repo.id}/issues?state=weird", headers=user())
            assert bad_state.status_code == 422

    async def test_metrics_404_before_sync(self, client, container):
        repo = await seed_repo(container)
        async with client as c:
            response = await c.get(f"/api/v1/repos/{repo.id}/metrics", headers=user())
        assert response.status_code == 404


class TestContextEndpoints:
    async def test_search(self, client, container):
        repo = await seed_repo(container)
        container.embeddings.matches = [
            ChunkMatch(
                document_id=uuid4(), path="README.md", title="R", doc_type="README",
                excerpt="hello", score=0.9,
            )
        ]
        async with client as c:
            response = await c.post(
                f"/api/v1/repos/{repo.id}/search", json={"query": "hello"}, headers=user()
            )
        assert response.json()[0]["path"] == "README.md"

    async def test_search_unsynced_conflict(self, client, container):
        repo = await seed_repo(container, synced=False)
        async with client as c:
            response = await c.post(
                f"/api/v1/repos/{repo.id}/search", json={"query": "hello"}, headers=user()
            )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "repository_not_synced"

    async def test_ask_grounded(self, client, container):
        repo = await seed_repo(container)
        container.embeddings.matches = [
            ChunkMatch(
                document_id=uuid4(), path="README.md", title="R", doc_type="README",
                excerpt="hello", score=0.9,
            )
        ]
        async with client as c:
            response = await c.post(
                f"/api/v1/repos/{repo.id}/ask",
                json={"question": "what is this?"},
                headers=user(),
            )
        body = response.json()
        assert body["grounded"] is True
        assert body["sources"][0]["path"] == "README.md"

    async def test_context_pack(self, client, container):
        repo = await seed_repo(container)
        async with client as c:
            response = await c.post(
                f"/api/v1/repos/{repo.id}/context-pack",
                json={"query": "implement opencl backend"},
                headers=user(),
            )
        body = response.json()
        assert body["mode"] == "project_intelligence"
        assert "cyberdyne/a" in body["repository_summary"]


class TestOpenApiContract:
    async def test_all_spec_endpoints_documented(self, client):
        async with client as c:
            spec = (await c.get("/openapi.json")).json()
        paths = set(spec["paths"].keys())
        expected = {
            "/api/v1/github/connect",
            "/api/v1/github/connections",
            "/api/v1/github/connections/{connection_id}/test",
            "/api/v1/github/connections/{connection_id}",
            "/api/v1/repos",
            "/api/v1/repos/{repo_id}",
            "/api/v1/repos/{repo_id}/sync",
            "/api/v1/repos/{repo_id}/sync-status",
            "/api/v1/repos/{repo_id}/summary",
            "/api/v1/repos/{repo_id}/docs",
            "/api/v1/repos/{repo_id}/docs/{doc_id}",
            "/api/v1/repos/{repo_id}/openspec",
            "/api/v1/repos/{repo_id}/issues",
            "/api/v1/repos/{repo_id}/pull-requests",
            "/api/v1/repos/{repo_id}/files",
            "/api/v1/repos/{repo_id}/metrics",
            "/api/v1/repos/{repo_id}/search",
            "/api/v1/repos/{repo_id}/ask",
            "/api/v1/repos/{repo_id}/context-pack",
            "/api/v1/health",
        }
        missing = expected - paths
        assert not missing, f"undocumented endpoints: {missing}"

    async def test_protected_endpoints_declare_bearer_security(self, client):
        async with client as c:
            spec = (await c.get("/openapi.json")).json()
        repos_get = spec["paths"]["/api/v1/repos"]["get"]
        assert "security" in repos_get
        health_get = spec["paths"]["/api/v1/health"]["get"]
        assert "security" not in health_get
