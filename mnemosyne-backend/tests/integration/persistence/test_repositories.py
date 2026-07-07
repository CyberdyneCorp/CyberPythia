"""Integration tests for Postgres repository adapters (real Postgres)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.domain.entities.audit_record import AuditRecord
from app.domain.entities.context_pack import ContextPack, DocRef
from app.domain.entities.document import Document
from app.domain.entities.github_connection import GitHubConnection
from app.domain.entities.issue import Issue
from app.domain.entities.openspec_change import OpenSpecChange
from app.domain.entities.pull_request import PullRequest
from app.domain.entities.repository import Repository
from app.domain.entities.source_file import SourceFile
from app.domain.entities.sync_job import SyncJob
from app.domain.value_objects.enums import (
    DocumentType,
    IndexingMode,
    IssueState,
    OpenSpecStatus,
    PullRequestState,
    RepositoryVisibility,
    SyncStatus,
)
from app.domain.value_objects.full_name import RepositoryFullName
from app.infrastructure.persistence.repositories.connections import PostgresConnectionRepository
from app.infrastructure.persistence.repositories.documents import (
    PostgresDocumentRepository,
    PostgresOpenSpecRepository,
)
from app.infrastructure.persistence.repositories.misc import (
    PostgresAuditRepository,
    PostgresContextPackRepository,
    PostgresFileRepository,
    PostgresMetricsRepository,
    PostgresSyncJobRepository,
)
from app.infrastructure.persistence.repositories.repositories import PostgresRepositoryRepository
from app.infrastructure.persistence.repositories.work_items import (
    PostgresIssueRepository,
    PostgresPullRequestRepository,
)

NOW = datetime(2026, 7, 7, 12, 0, tzinfo=UTC)


def make_connection() -> GitHubConnection:
    return GitHubConnection(
        id=uuid4(),
        owner="cyberdyne",
        owner_type="Organization",
        encrypted_token=b"ciphertext",
        token_hint="ab12",
        permissions=["contents", "issues", "pull_requests", "metadata"],
        created_at=NOW,
        updated_at=NOW,
    )


def make_repo(connection_id, full_name="cyberdyne/matforge", github_id=1) -> Repository:
    return Repository(
        id=uuid4(),
        connection_id=connection_id,
        github_id=github_id,
        full_name=RepositoryFullName(full_name),
        description="d",
        visibility=RepositoryVisibility.PRIVATE,
        default_branch="main",
        primary_language="Python",
        archived=False,
        github_updated_at=NOW,
    )


async def seed_repo(session_factory) -> Repository:
    conn = make_connection()
    await PostgresConnectionRepository(session_factory).save(conn)
    repo = make_repo(conn.id)
    await PostgresRepositoryRepository(session_factory).save(repo)
    return repo


class TestConnections:
    async def test_roundtrip_and_lookup(self, session_factory):
        repo_adapter = PostgresConnectionRepository(session_factory)
        conn = make_connection()
        await repo_adapter.save(conn)

        loaded = await repo_adapter.get_by_owner("cyberdyne")
        assert loaded is not None
        assert loaded.encrypted_token == b"ciphertext"
        assert loaded.permissions == ["contents", "issues", "pull_requests", "metadata"]

    async def test_update_and_delete(self, session_factory):
        adapter = PostgresConnectionRepository(session_factory)
        conn = make_connection()
        await adapter.save(conn)
        conn.mark_broken()
        await adapter.save(conn)
        loaded = await adapter.get(conn.id)
        assert loaded.status.value == "broken"

        await adapter.delete(conn.id)
        assert await adapter.get(conn.id) is None


class TestRepositories:
    async def test_discovery_rerun_does_not_duplicate(self, session_factory):
        conn = make_connection()
        await PostgresConnectionRepository(session_factory).save(conn)
        adapter = PostgresRepositoryRepository(session_factory)

        first = make_repo(conn.id)
        await adapter.save(first)
        rediscovered = make_repo(conn.id)  # new uuid, same github_id
        await adapter.save(rediscovered)

        all_repos = await adapter.list_all()
        assert len(all_repos) == 1
        assert rediscovered.id == first.id  # id reconciled to existing row

    async def test_enabled_only_filter(self, session_factory):
        conn = make_connection()
        await PostgresConnectionRepository(session_factory).save(conn)
        adapter = PostgresRepositoryRepository(session_factory)
        enabled = make_repo(conn.id, "cyberdyne/a", 1)
        enabled.enable(IndexingMode.PROJECT_INTELLIGENCE)
        disabled = make_repo(conn.id, "cyberdyne/b", 2)
        await adapter.save_many([enabled, disabled])

        assert len(await adapter.list_all()) == 2
        only_enabled = await adapter.list_all(enabled_only=True)
        assert [str(r.full_name) for r in only_enabled] == ["cyberdyne/a"]


class TestDocuments:
    async def test_upsert_by_path_and_delete_missing(self, session_factory):
        repo = await seed_repo(session_factory)
        adapter = PostgresDocumentRepository(session_factory)

        doc = Document(
            id=uuid4(),
            repository_id=repo.id,
            path="README.md",
            type=DocumentType.README,
            title="README",
            content="hello",
            content_hash="h1",
            last_commit_sha="sha1",
            captured_at=NOW,
        )
        await adapter.save(doc)
        updated = Document(
            id=uuid4(),
            repository_id=repo.id,
            path="README.md",
            type=DocumentType.README,
            title="README",
            content="hello v2",
            content_hash="h2",
            last_commit_sha="sha2",
            captured_at=NOW,
        )
        await adapter.save(updated)

        docs = await adapter.list_by_repository(repo.id)
        assert len(docs) == 1
        assert docs[0].content == "hello v2"

        gone = Document(
            id=uuid4(),
            repository_id=repo.id,
            path="docs/old.md",
            type=DocumentType.DOCS,
            title="old",
            content="x",
            content_hash="h3",
            last_commit_sha=None,
            captured_at=NOW,
        )
        await adapter.save(gone)
        removed = await adapter.delete_missing(repo.id, {"README.md"})
        assert removed == 1
        assert [d.path for d in await adapter.list_by_repository(repo.id)] == ["README.md"]


class TestOpenSpec:
    async def test_upsert_by_change_id(self, session_factory):
        repo = await seed_repo(session_factory)
        adapter = PostgresOpenSpecRepository(session_factory)
        change = OpenSpecChange(
            id=uuid4(),
            repository_id=repo.id,
            change_id="add-x",
            path="openspec/changes/add-x",
            status=OpenSpecStatus.ACTIVE,
            proposal="p",
            affected_specs=["auth"],
        )
        await adapter.save(change)
        change2 = OpenSpecChange(
            id=uuid4(),
            repository_id=repo.id,
            change_id="add-x",
            path="openspec/changes/add-x",
            status=OpenSpecStatus.ARCHIVED,
        )
        await adapter.save(change2)

        changes = await adapter.list_by_repository(repo.id)
        assert len(changes) == 1
        assert changes[0].status is OpenSpecStatus.ARCHIVED


class TestWorkItems:
    async def test_issue_upsert_and_filters(self, session_factory):
        repo = await seed_repo(session_factory)
        adapter = PostgresIssueRepository(session_factory)
        issues = [
            Issue(
                id=uuid4(),
                repository_id=repo.id,
                github_issue_id=n,
                number=n,
                title=f"i{n}",
                body=None,
                state=IssueState.OPEN if n % 2 else IssueState.CLOSED,
                author="alice",
                labels=["bug"] if n == 1 else [],
                created_at=NOW - timedelta(days=n),
                closed_at=None if n % 2 else NOW,
            )
            for n in range(1, 5)
        ]
        await adapter.save_many(issues)
        await adapter.save_many(issues)  # idempotent re-sync

        assert len(await adapter.list_by_repository(repo.id)) == 4
        assert len(await adapter.list_by_repository(repo.id, state="open")) == 2
        assert [i.number for i in await adapter.list_by_repository(repo.id, label="bug")] == [1]
        found = await adapter.get_by_number(repo.id, 3)
        assert found is not None and found.title == "i3"

    async def test_pr_roundtrip(self, session_factory):
        repo = await seed_repo(session_factory)
        adapter = PostgresPullRequestRepository(session_factory)
        pr = PullRequest(
            id=uuid4(),
            repository_id=repo.id,
            github_pr_id=100,
            number=7,
            title="pr",
            body=None,
            state=PullRequestState.MERGED,
            merged=True,
            author="bob",
            reviewers=["alice"],
            created_at=NOW - timedelta(days=1),
            merged_at=NOW,
            first_review_at=NOW - timedelta(hours=20),
            additions=10,
            deletions=2,
        )
        await adapter.save_many([pr])
        loaded = await adapter.get_by_number(repo.id, 7)
        assert loaded is not None
        assert loaded.merged and loaded.reviewers == ["alice"]
        assert (await adapter.list_by_repository(repo.id, author="bob"))[0].number == 7


class TestFilesSyncJobsMetrics:
    async def test_replace_tree(self, session_factory):
        repo = await seed_repo(session_factory)
        adapter = PostgresFileRepository(session_factory)
        files1 = [
            SourceFile(
                id=uuid4(),
                repository_id=repo.id,
                path="src/a.py",
                extension="py",
                language="Python",
                size_bytes=10,
                sha="s1",
                last_seen_at=NOW,
            )
        ]
        await adapter.replace_tree(repo.id, files1)
        files2 = [
            SourceFile(
                id=uuid4(),
                repository_id=repo.id,
                path="pyproject.toml",
                extension="toml",
                language=None,
                size_bytes=5,
                sha="s2",
                is_important=True,
                important_kind="dependency_manifest",
                last_seen_at=NOW,
            )
        ]
        await adapter.replace_tree(repo.id, files2)
        files = await adapter.list_by_repository(repo.id)
        assert [f.path for f in files] == ["pyproject.toml"]
        assert files[0].is_important

    async def test_sync_job_roundtrip(self, session_factory):
        repo = await seed_repo(session_factory)
        adapter = PostgresSyncJobRepository(session_factory)
        job = SyncJob(id=uuid4(), repository_id=repo.id, mode=IndexingMode.PROJECT_INTELLIGENCE)
        job.plan()
        job.start(NOW)
        await adapter.save(job)

        loaded = await adapter.get(job.id)
        assert loaded is not None
        assert loaded.status is SyncStatus.RUNNING
        assert [s.step for s in loaded.steps] == [s.step for s in job.steps]
        assert (await adapter.get_latest(repo.id)).id == job.id

    async def test_metrics_upsert(self, session_factory):
        repo = await seed_repo(session_factory)
        adapter = PostgresMetricsRepository(session_factory)
        await adapter.save(
            repo.id,
            issue_metrics={"avg": 1.0},
            pr_metrics={},
            summary={"open_issues": 3},
            computed_at=NOW,
        )
        await adapter.save(
            repo.id,
            issue_metrics={"avg": 2.0},
            pr_metrics={},
            summary={"open_issues": 4},
            computed_at=NOW,
        )
        loaded = await adapter.get(repo.id)
        assert loaded["issue_metrics"] == {"avg": 2.0}
        assert loaded["summary"]["open_issues"] == 4


class TestContextPackCache:
    async def test_cache_hit_requires_same_sync_timestamp(self, session_factory):
        repo = await seed_repo(session_factory)
        adapter = PostgresContextPackRepository(session_factory)
        pack = ContextPack(
            id=uuid4(),
            repository_id=repo.id,
            query="implement OpenCL backend",
            mode=IndexingMode.PROJECT_INTELLIGENCE,
            repository_summary="summary",
            relevant_docs=[DocRef(path="README.md", title="R", doc_type="README", score=0.9)],
            sync_timestamp=NOW,
            created_at=NOW,
        )
        await adapter.save(pack)

        hit = await adapter.find_cached(
            repo.id, "Implement opencl BACKEND", "project_intelligence", NOW.isoformat()
        )
        assert hit is not None  # query matching is case/whitespace-insensitive
        assert hit.relevant_docs[0].path == "README.md"

        stale = await adapter.find_cached(
            repo.id,
            "implement OpenCL backend",
            "project_intelligence",
            (NOW + timedelta(hours=1)).isoformat(),
        )
        assert stale is None


class TestAudit:
    async def test_record_and_list(self, session_factory):
        adapter = PostgresAuditRepository(session_factory)
        await adapter.record(
            AuditRecord(
                id=uuid4(),
                subject="user-1",
                client_id=None,
                operation="github.connect",
                target="cyberdyne",
                outcome="ok",
                occurred_at=NOW,
            )
        )
        entries = await adapter.list_recent()
        assert entries[0].operation == "github.connect"


class TestAppConnectionAndWebhooks:
    async def test_github_app_connection_roundtrip(self, session_factory):
        from app.domain.value_objects.enums import ConnectionKind
        from app.infrastructure.persistence.repositories.connections import (
            PostgresConnectionRepository,
        )

        adapter = PostgresConnectionRepository(session_factory)
        conn = GitHubConnection(
            id=uuid4(), owner="cyberdyne", owner_type="Organization",
            kind=ConnectionKind.GITHUB_APP, app_id="12345", installation_id="99",
            encrypted_private_key=b"pk-cipher", encrypted_webhook_secret=b"wh-cipher",
            permissions=["contents", "issues"], created_at=NOW, updated_at=NOW,
        )
        await adapter.save(conn)
        loaded = await adapter.get(conn.id)
        assert loaded.kind is ConnectionKind.GITHUB_APP
        assert loaded.installation_id == "99"
        assert loaded.encrypted_private_key == b"pk-cipher"
        assert loaded.encrypted_token is None

    async def test_webhook_delivery_idempotency(self, session_factory):
        from app.domain.entities.webhook_delivery import WebhookDelivery
        from app.infrastructure.persistence.repositories.misc import (
            PostgresWebhookDeliveryRepository,
        )

        adapter = PostgresWebhookDeliveryRepository(session_factory)
        assert not await adapter.exists("delivery-1")
        await adapter.record(
            WebhookDelivery(
                id=uuid4(), delivery_id="delivery-1", event="issues", action="opened",
                repository_full_name="cyberdyne/a", outcome="processed", received_at=NOW,
            )
        )
        assert await adapter.exists("delivery-1")
        recent = await adapter.list_recent()
        assert recent[0].event == "issues"
