"""Interface tests for the REST API (spec: rest-api). Fakes behind a real app."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.application.audit import AuditService
from app.application.use_cases.code import CodeUseCases
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
    FakeSourceChunkPort,
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

    async def embed_source_chunks(self, repository_id, chunks):
        return len(chunks)

    async def search_code(self, repository_id, query, *, limit=8):
        return getattr(self, "code_matches", [])[:limit]


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

    async def list_all(self):
        return dict(self.data)

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
    source_chunks = FakeSourceChunkPort()
    from app.application.metrics_recompute import MetricsRecomputeService
    from app.application.use_cases.incremental_sync import IncrementalSyncUseCases
    from app.application.use_cases.process_webhook import ProcessWebhookDelivery
    from tests.unit.application.test_process_webhook import FakeDeliveryPort

    metrics_recompute = MetricsRecomputeService(
        issues, prs, documents, openspec, metrics_store
    )
    incremental = IncrementalSyncUseCases(
        repositories, issues, prs, github, connection_uc, metrics_recompute
    )
    webhook_deliveries = FakeDeliveryPort()
    process_webhook = ProcessWebhookDelivery(
        webhook_deliveries, connections, incremental, repo_uc
    )
    code_uc = CodeUseCases(
        repositories=repositories,
        files=files,
        source_chunks=source_chunks,
        embeddings=embeddings,
        audit=AuditService(audit_port),
    )
    from app.application.use_cases.delivery_intelligence import DeliveryIntelligenceService
    from app.application.use_cases.intelligence import IntelligenceService
    from app.domain.services.repository_health import RepositoryHealthService
    from app.domain.services.repository_signals import RepositorySignalsService
    from tests.unit.application.test_delivery_intelligence import (
        FakeHistoryPort,
        FakeMilestonePort,
    )

    intelligence = IntelligenceService(
        repositories, files, metrics_store,
        RepositorySignalsService(), RepositoryHealthService(),
    )
    metrics_history = FakeHistoryPort()
    milestones_port = FakeMilestonePort()
    delivery_intelligence = DeliveryIntelligenceService(
        repositories, issues, prs, milestones_port, metrics_history,
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
        code_use_cases=code_uc,
        source_chunks=source_chunks,
        webhook_deliveries=webhook_deliveries,
        process_webhook=process_webhook,
        intelligence=intelligence,
        delivery_intelligence=delivery_intelligence,
        metrics_history=metrics_history,
        milestones=milestones_port,
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
            "/api/v1/repos/{repo_id}/code-search",
            "/api/v1/repos/{repo_id}/symbols",
            "/api/v1/repos/{repo_id}/files/{file_id}/content",
            "/api/v1/repos/{repo_id}/files/{file_id}/related",
            "/api/v1/github/app/connect",
            "/api/v1/github/app/installations/{connection_id}/repos",
            "/api/v1/webhooks/github",
            "/api/v1/admin/webhook-deliveries",
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
        webhook_post = spec["paths"]["/api/v1/webhooks/github"]["post"]
        assert "security" not in webhook_post


class TestCors:
    """The web app is served from a different origin than the API (prod bug 2026-07-07)."""

    async def test_preflight_allows_the_web_origin(self, client):
        async with client as c:
            response = await c.options(
                "/api/v1/repos",
                headers={
                    "Origin": "http://localhost:5173",
                    "Access-Control-Request-Method": "GET",
                    "Access-Control-Request-Headers": "authorization",
                },
            )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
        assert "authorization" in response.headers["access-control-allow-headers"].lower()

    async def test_unknown_origin_not_allowed(self, client):
        async with client as c:
            response = await c.options(
                "/api/v1/repos",
                headers={
                    "Origin": "https://evil.example",
                    "Access-Control-Request-Method": "GET",
                },
            )
        assert "access-control-allow-origin" not in response.headers


class TestCodeEndpoints:
    async def test_code_search_on_code_repo(self, client, container):
        from app.domain.ports.infra_ports import CodeChunkMatch

        repo = await seed_repo(container, mode=IndexingMode.CODE_CONTEXT)
        container.embeddings.code_matches = [
            CodeChunkMatch(
                chunk_id=uuid4(), file_id=uuid4(), path="src/gpu.cpp",
                symbol_name="dispatch", chunk_type="function",
                start_line=1, end_line=5, excerpt="void dispatch()", score=0.9,
            )
        ]
        async with client as c:
            response = await c.post(
                f"/api/v1/repos/{repo.id}/code-search",
                json={"query": "dispatch"}, headers=user(),
            )
        assert response.status_code == 200
        assert response.json()[0]["symbol_name"] == "dispatch"

    async def test_code_search_on_non_code_repo_409(self, client, container):
        repo = await seed_repo(container, mode=IndexingMode.PROJECT_INTELLIGENCE)
        async with client as c:
            response = await c.post(
                f"/api/v1/repos/{repo.id}/code-search",
                json={"query": "dispatch"}, headers=user(),
            )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "source_not_indexed"

    async def test_file_content_and_audit(self, client, container):
        from app.domain.entities.source_file import SourceFile

        repo = await seed_repo(container, mode=IndexingMode.CODE_CONTEXT)
        f = SourceFile(
            id=uuid4(), repository_id=repo.id, path="src/gpu.cpp", extension="cpp",
            language="C++", size_bytes=20, sha="s", content="void dispatch(){}",
            content_captured=True, content_hash="h",
        )
        await container.files.replace_tree(repo.id, [f])
        async with client as c:
            response = await c.get(
                f"/api/v1/repos/{repo.id}/files/{f.id}/content", headers=user()
            )
        assert response.status_code == 200
        assert response.json()["content"] == "void dispatch(){}"
        assert any(r.operation == "code.file_content" for r in container.audit_port.records)

    async def test_file_content_quarantined_404(self, client, container):
        from app.domain.entities.source_file import SourceFile

        repo = await seed_repo(container, mode=IndexingMode.CODE_CONTEXT)
        f = SourceFile(
            id=uuid4(), repository_id=repo.id, path="src/keys.py", extension="py",
            language="Python", size_bytes=20, sha="s", quarantined=True,
            content=None, content_captured=False,
        )
        await container.files.replace_tree(repo.id, [f])
        async with client as c:
            response = await c.get(
                f"/api/v1/repos/{repo.id}/files/{f.id}/content", headers=user()
            )
        assert response.status_code == 404

    async def test_symbols_requires_entitlement(self, client, container):
        repo = await seed_repo(container, mode=IndexingMode.CODE_CONTEXT)
        async with client as c:
            no_token = await c.get(f"/api/v1/repos/{repo.id}/symbols")
            denied = await c.get(
                f"/api/v1/repos/{repo.id}/symbols",
                headers={"Authorization": "Bearer unentitled-token"},
            )
        assert no_token.status_code == 401
        assert denied.status_code == 403


class TestGitHubAppAndWebhookEndpoints:
    async def _seed_app_connection(self, container, installation_id="99", secret="whsec"):
        from app.domain.entities.github_connection import GitHubConnection
        from app.domain.value_objects.enums import ConnectionKind

        conn = GitHubConnection(
            id=uuid4(), owner="cyberdyne", owner_type="Organization",
            kind=ConnectionKind.GITHUB_APP, app_id="12345", installation_id=installation_id,
            encrypted_private_key=b"enc:pk",
            encrypted_webhook_secret=f"enc:{secret}".encode(),
        )
        await container.connections.save(conn)
        return conn

    async def test_app_connect_requires_admin(self, client):
        body = {"app_id": "1", "installation_id": "99",
                "private_key": "-" * 50, "webhook_secret": "s"}
        async with client as c:
            no = await c.post("/api/v1/github/app/connect", json=body, headers=user())
        assert no.status_code == 403

    async def test_webhook_valid_signature_dispatches(self, client, container):
        import json as _json

        from app.domain.services.webhook_signature import compute_signature

        await self._seed_app_connection(container)
        # an enabled synced repo so a push enqueues a sync
        await seed_repo(container)
        container.repositories.items[  # ensure full_name matches payload
            next(iter(container.repositories.items))
        ].enabled = True
        payload = {
            "installation": {"id": 99},
            "repository": {"full_name": "cyberdyne/a"},
        }
        body = _json.dumps(payload).encode()
        sig = compute_signature("whsec", body)
        async with client as c:
            resp = await c.post(
                "/api/v1/webhooks/github",
                content=body,
                headers={
                    "X-Hub-Signature-256": sig,
                    "X-GitHub-Event": "push",
                    "X-GitHub-Delivery": "delivery-abc",
                    "Content-Type": "application/json",
                },
            )
        assert resp.status_code == 200
        assert resp.text == "processed"

    async def test_webhook_invalid_signature_401(self, client, container):
        import json as _json

        await self._seed_app_connection(container)
        body = _json.dumps({"installation": {"id": 99}}).encode()
        async with client as c:
            resp = await c.post(
                "/api/v1/webhooks/github",
                content=body,
                headers={
                    "X-Hub-Signature-256": "sha256=deadbeef",
                    "X-GitHub-Event": "push",
                    "X-GitHub-Delivery": "d2",
                },
            )
        assert resp.status_code == 401

    async def test_webhook_missing_signature_401(self, client, container):
        import json as _json

        await self._seed_app_connection(container)
        body = _json.dumps({"installation": {"id": 99}}).encode()
        async with client as c:
            resp = await c.post(
                "/api/v1/webhooks/github", content=body,
                headers={"X-GitHub-Event": "push", "X-GitHub-Delivery": "d3"},
            )
        assert resp.status_code == 401

    async def test_webhook_deliveries_admin_only(self, client):
        async with client as c:
            no_token = await c.get("/api/v1/admin/webhook-deliveries")
            denied = await c.get(
                "/api/v1/admin/webhook-deliveries", headers=user()
            )
        assert no_token.status_code == 401
        assert denied.status_code == 403
