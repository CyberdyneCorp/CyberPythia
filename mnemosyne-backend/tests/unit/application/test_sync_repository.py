"""Unit tests for the sync orchestrator (spec: repository-sync)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.application.use_cases.github_connections import GitHubConnectionUseCases
from app.application.use_cases.sync_repository import (
    MetricsWriter,
    SyncRepositoryUseCase,
    _chunk_markdown,
)
from app.domain.entities.repository import Repository
from app.domain.entities.sync_job import SyncJob
from app.domain.ports.github_port import (
    GitHubFileData,
    GitHubIssueData,
    GitHubPullRequestData,
    GitHubRepoData,
)
from app.domain.services.code_chunker import HeuristicCodeChunker
from app.domain.value_objects.enums import (
    EmbeddingStatus,
    IndexingMode,
    RepositoryVisibility,
    SyncStatus,
    SyncStep,
)
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

NOW = datetime(2026, 7, 7, tzinfo=UTC)


class FakeEmbeddings:
    def __init__(self):
        self.embedded: dict = {}
        self.code_embedded: list = []

    async def embed_document(self, document_id, repository_id, chunks):
        self.embedded[document_id] = chunks
        return len(chunks)

    async def delete_document(self, document_id):
        self.embedded.pop(document_id, None)

    async def search(self, repository_id, query, *, limit=8):
        return []

    async def embed_source_chunks(self, repository_id, chunks):
        self.code_embedded.extend(chunks)
        return len(chunks)

    async def search_code(self, repository_id, query, *, limit=8):
        return []


class FakeMetricsStore:
    def __init__(self):
        self.saved = {}

    async def save(self, repository_id, *, issue_metrics, pr_metrics, summary, computed_at):
        self.saved[repository_id] = {
            "issue_metrics": issue_metrics,
            "pr_metrics": pr_metrics,
            "summary": summary,
            "computed_at": computed_at,
        }

    async def get(self, repository_id):
        return self.saved.get(repository_id)


def gh_issue(number, *, is_pr=False, state="open"):
    return GitHubIssueData(
        github_id=number,
        number=number,
        title=f"i{number}",
        body=None,
        state=state,
        author="alice",
        labels=[],
        assignees=[],
        milestone=None,
        created_at=NOW,
        updated_at=NOW,
        closed_at=NOW if state == "closed" else None,
        comments_count=0,
        is_pull_request=is_pr,
    )


def gh_pr(number):
    return GitHubPullRequestData(
        github_id=number,
        number=number,
        title=f"pr{number}",
        body=None,
        state="merged",
        merged=True,
        author="bob",
        reviewers=["carol"],
        created_at=NOW,
        updated_at=NOW,
        closed_at=NOW,
        merged_at=NOW,
        first_review_at=NOW,
        changed_files=1,
        additions=5,
        deletions=1,
        review_decision="APPROVED",
    )


@pytest.fixture
def env():
    github = FakeGitHub()
    github.repos = [
        GitHubRepoData(
            github_id=1,
            full_name="cyberdyne/a",
            description="demo",
            visibility="private",
            default_branch="main",
            primary_language="Python",
            archived=False,
            updated_at=NOW,
        )
    ]
    github.tree = [
        GitHubFileData(path="README.md", sha="s1", size=10, is_binary=False),
        GitHubFileData(path="docs/setup.md", sha="s2", size=10, is_binary=False),
        GitHubFileData(path="secrets/creds.md", sha="s3", size=10, is_binary=False),
        GitHubFileData(path="openspec/changes/add-x/proposal.md", sha="s4", size=5, is_binary=False),
        GitHubFileData(path="pyproject.toml", sha="s5", size=5, is_binary=False),
        GitHubFileData(path="src/app.py", sha="s6", size=5, is_binary=False),
        GitHubFileData(path="logo.png", sha="s7", size=5, is_binary=True),
    ]
    github.files = {
        "README.md": "# Demo\n\nHello world.",
        "docs/setup.md": "# Setup\n\nRun just install.",
        "secrets/creds.md": "password = \"super-secret-value-123456\"",
        "openspec/changes/add-x/proposal.md": "# Proposal add-x",
    }
    github.issues = [gh_issue(1), gh_issue(2, state="closed"), gh_issue(3, is_pr=True)]
    github.pull_requests = [gh_pr(10)]

    connections = FakeConnectionPort()
    connection_uc = GitHubConnectionUseCases(connections, github, FakeCipher())
    repositories = FakeRepositoryPort()
    documents = FakeDocumentPort()
    openspec = FakeOpenSpecPort()
    issues = FakeIssuePort()
    prs = FakePullRequestPort()
    files = FakeFilePort()
    sync_jobs = FakeSyncJobPort()
    embeddings = FakeEmbeddings()
    metrics_store = FakeMetricsStore()
    source_chunks = FakeSourceChunkPort()

    use_case = SyncRepositoryUseCase(
        repositories=repositories,
        documents=documents,
        openspec=openspec,
        issues=issues,
        pull_requests=prs,
        files=files,
        sync_jobs=sync_jobs,
        github=github,
        connection_use_cases=connection_uc,
        sync_lock=FakeSyncLock(),
        storage=FakeStorage(),
        embeddings=embeddings,
        metrics_writer=MetricsWriter(store=metrics_store),
        source_chunks=source_chunks,
        code_chunker=HeuristicCodeChunker(),
    )
    return {
        "use_case": use_case,
        "github": github,
        "connection_uc": connection_uc,
        "repositories": repositories,
        "documents": documents,
        "openspec": openspec,
        "issues": issues,
        "prs": prs,
        "files": files,
        "sync_jobs": sync_jobs,
        "embeddings": embeddings,
        "metrics_store": metrics_store,
        "source_chunks": source_chunks,
    }


async def seed(env, mode=IndexingMode.PROJECT_INTELLIGENCE):
    connection = await env["connection_uc"].connect("ghp_secret_ab12")
    repo = Repository(
        id=uuid4(),
        connection_id=connection.id,
        github_id=1,
        full_name=RepositoryFullName("cyberdyne/a"),
        description=None,
        visibility=RepositoryVisibility.PRIVATE,
        default_branch="main",
        primary_language=None,
        archived=False,
        github_updated_at=None,
        enabled=True,
        indexing_mode=mode,
    )
    await env["repositories"].save(repo)
    job = SyncJob(id=uuid4(), repository_id=repo.id, mode=mode)
    job.plan()
    await env["sync_jobs"].save(job)
    return repo, job


class TestFullSync:
    async def test_project_intelligence_sync_succeeds(self, env):
        repo, job = await seed(env)
        result = await env["use_case"].run(repo.id, job.id)

        assert result.status is SyncStatus.SUCCEEDED
        docs = await env["documents"].list_by_repository(repo.id)
        paths = [d.path for d in docs]
        assert "README.md" in paths and "docs/setup.md" in paths
        assert "secrets/creds.md" not in paths  # default denylist (spec: ignore rules)

        issues = await env["issues"].list_by_repository(repo.id)
        assert [i.number for i in issues] == [2, 1]  # PR-flavored issue excluded

        prs = await env["prs"].list_by_repository(repo.id)
        assert [p.number for p in prs] == [10]

        changes = await env["openspec"].list_by_repository(repo.id)
        assert changes[0].change_id == "add-x"
        assert changes[0].proposal == "# Proposal add-x"

        assert not env["files"].trees  # file tree not captured in this mode
        assert (await env["repositories"].get(repo.id)).last_synced_at is not None

    async def test_docs_only_mode_skips_issues_and_prs(self, env):
        repo, job = await seed(env, IndexingMode.DOCS_ONLY)
        result = await env["use_case"].run(repo.id, job.id)
        assert result.status is SyncStatus.SUCCEEDED
        assert await env["issues"].list_by_repository(repo.id) == []
        assert await env["prs"].list_by_repository(repo.id) == []

    async def test_code_metadata_mode_captures_tree_with_importance(self, env):
        repo, job = await seed(env, IndexingMode.CODE_METADATA)
        await env["use_case"].run(repo.id, job.id)
        files = await env["files"].list_by_repository(repo.id)
        by_path = {f.path: f for f in files}
        assert by_path["pyproject.toml"].is_important
        assert by_path["pyproject.toml"].important_kind == "dependency_manifest"
        assert by_path["logo.png"].is_binary
        assert "secrets/creds.md" not in by_path


class TestQuarantineAndEmbeddings:
    async def test_secret_document_quarantined_when_not_denylisted(self, env):
        env["github"].tree.append(
            type(env["github"].tree[0])(path="docs/keys.md", sha="s9", size=9, is_binary=False)
        )
        env["github"].files["docs/keys.md"] = 'aws = "AKIAIOSFODNN7EXAMPLE"\nkey=AKIAIOSFODNN7EXAMPLE'
        repo, job = await seed(env)
        await env["use_case"].run(repo.id, job.id)

        quarantined = await env["documents"].get_by_path(repo.id, "docs/keys.md")
        assert quarantined.quarantined
        assert quarantined.content is None  # metadata only (spec)
        assert quarantined.embedding_status is EmbeddingStatus.SKIPPED
        assert quarantined.id not in env["embeddings"].embedded

    async def test_embeddings_only_for_pending_docs(self, env):
        repo, job = await seed(env)
        await env["use_case"].run(repo.id, job.id)
        readme = await env["documents"].get_by_path(repo.id, "README.md")
        assert readme.embedding_status is EmbeddingStatus.EMBEDDED
        assert env["embeddings"].embedded[readme.id]

    async def test_resync_skips_unchanged_documents(self, env):
        repo, job = await seed(env)
        await env["use_case"].run(repo.id, job.id)
        first_embed_count = len(env["embeddings"].embedded)

        job2 = SyncJob(id=uuid4(), repository_id=repo.id, mode=repo.indexing_mode)
        job2.plan()
        await env["sync_jobs"].save(job2)
        await env["use_case"].run(repo.id, job2.id)
        assert len(env["embeddings"].embedded) == first_embed_count  # no re-embed


class TestFailureHandling:
    async def test_step_failure_recorded_and_others_retained(self, env):
        async def boom(token, full_name):
            raise RuntimeError("issues API down")

        env["github"].list_issues = boom
        repo, job = await seed(env)
        result = await env["use_case"].run(repo.id, job.id)

        assert result.status is SyncStatus.FAILED
        failed = {s.step for s in result.failed_steps}
        assert failed == {SyncStep.ISSUES}
        assert result.step_result(SyncStep.DOCS).status is SyncStatus.SUCCEEDED
        # docs data retained despite failed sync (spec: partial failure)
        assert await env["documents"].list_by_repository(repo.id)
        # repository not marked synced on failure
        assert (await env["repositories"].get(repo.id)).last_synced_at is None

    async def test_lock_released_after_run(self, env):
        repo, job = await seed(env)
        await env["use_case"].run(repo.id, job.id)
        # a second run acquires the lock fine
        job2 = SyncJob(id=uuid4(), repository_id=repo.id, mode=repo.indexing_mode)
        job2.plan()
        await env["sync_jobs"].save(job2)
        result = await env["use_case"].run(repo.id, job2.id)
        assert result.status is SyncStatus.SUCCEEDED


class TestMetricsStep:
    async def test_metrics_and_summary_persisted(self, env):
        repo, job = await seed(env)
        await env["use_case"].run(repo.id, job.id)
        stored = env["metrics_store"].saved[repo.id]
        assert stored["summary"]["has_readme"] is True
        assert stored["summary"]["has_openspec"] is True
        assert stored["summary"]["open_issues"] == 1
        assert stored["summary"]["merged_prs"] == 1
        assert stored["issue_metrics"]["total"] == 2
        assert stored["computed_at"] is not None


class TestChunker:
    def test_chunks_by_heading(self):
        content = "# A\ntext a\n## B\ntext b\n## C\ntext c"
        chunks = _chunk_markdown(content)
        assert len(chunks) == 3
        assert chunks[0].startswith("# A")

    def test_oversized_section_split(self):
        content = "# Big\n" + ("x" * 15000)
        chunks = _chunk_markdown(content, max_chars=6000)
        assert len(chunks) == 3
        assert all(len(c) <= 6000 for c in chunks)

    def test_empty_content(self):
        assert _chunk_markdown("") == []
