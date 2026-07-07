"""Unit tests for context packs and repository Q&A (spec: context-packs)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.application.errors import RepositoryNotSyncedError, UnknownResourceError
from app.application.use_cases.context import ContextUseCases
from app.domain.entities.issue import Issue
from app.domain.entities.openspec_change import OpenSpecChange
from app.domain.entities.pull_request import PullRequest
from app.domain.entities.repository import Repository
from app.domain.entities.source_file import SourceFile
from app.domain.ports.infra_ports import ChunkMatch
from app.domain.value_objects.enums import (
    IndexingMode,
    IssueState,
    OpenSpecStatus,
    PullRequestState,
    RepositoryVisibility,
)
from app.domain.value_objects.full_name import RepositoryFullName
from tests.unit.application.fakes import (
    FakeDocumentPort,
    FakeFilePort,
    FakeIssuePort,
    FakeOpenSpecPort,
    FakePullRequestPort,
    FakeRepositoryPort,
)

NOW = datetime(2026, 7, 7, tzinfo=UTC)


class FakeSearchEmbeddings:
    def __init__(self):
        self.matches: list[ChunkMatch] = []
        self.code_matches: list = []

    async def embed_document(self, document_id, repository_id, chunks):
        return len(chunks)

    async def delete_document(self, document_id):
        pass

    async def search(self, repository_id, query, *, limit=8):
        return self.matches[:limit]

    async def embed_source_chunks(self, repository_id, chunks):
        return len(chunks)

    async def search_code(self, repository_id, query, *, limit=8):
        return self.code_matches[:limit]


class FakeContextPackPort:
    def __init__(self):
        self.saved = []

    async def save(self, pack):
        self.saved.append(pack)

    async def find_cached(self, repository_id, query, mode, sync_timestamp):
        for pack in self.saved:
            same = (
                pack.repository_id == repository_id
                and pack.query.strip().lower() == query.strip().lower()
                and pack.mode.value == mode
                and (pack.sync_timestamp.isoformat() if pack.sync_timestamp else "")
                == sync_timestamp
            )
            if same:
                return pack
        return None


class FakeAnswerer:
    def __init__(self):
        self.calls = []

    async def answer(self, question, context_blocks):
        self.calls.append((question, context_blocks))
        return f"Answer citing {len(context_blocks)} blocks."


class FakeMetricsStore:
    def __init__(self, summary=None):
        self.summary = summary

    async def get(self, repository_id):
        if self.summary is None:
            return None
        return {"summary": self.summary}


def make_repo(mode=IndexingMode.PROJECT_INTELLIGENCE, synced=True):
    return Repository(
        id=uuid4(),
        connection_id=uuid4(),
        github_id=1,
        full_name=RepositoryFullName("cyberdyne/matforge"),
        description="MATLAB LLVM compiler",
        visibility=RepositoryVisibility.PRIVATE,
        default_branch="main",
        primary_language="C++",
        archived=False,
        github_updated_at=NOW,
        enabled=True,
        indexing_mode=mode,
        last_synced_at=NOW if synced else None,
    )


@pytest.fixture
def env():
    repositories = FakeRepositoryPort()
    embeddings = FakeSearchEmbeddings()
    packs = FakeContextPackPort()
    issues = FakeIssuePort()
    prs = FakePullRequestPort()
    openspec = FakeOpenSpecPort()
    files = FakeFilePort()
    answerer = FakeAnswerer()
    use_cases = ContextUseCases(
        repositories=repositories,
        documents=FakeDocumentPort(),
        openspec=openspec,
        issues=issues,
        pull_requests=prs,
        files=files,
        context_packs=packs,
        embeddings=embeddings,
        answerer=answerer,
        metrics_store=FakeMetricsStore({"documents": 3, "open_issues": 1}),
    )
    return {
        "use_cases": use_cases,
        "repositories": repositories,
        "embeddings": embeddings,
        "packs": packs,
        "issues": issues,
        "prs": prs,
        "openspec": openspec,
        "files": files,
        "answerer": answerer,
    }


def doc_match(path="docs/gpu-backend.md", score=0.9):
    return ChunkMatch(
        document_id=uuid4(),
        path=path,
        title="GPU backend",
        doc_type="DOCS",
        excerpt="The GPU backend dispatches kernels...",
        score=score,
    )


async def seed_repo(env, **kw):
    repo = make_repo(**kw)
    await env["repositories"].save(repo)
    return repo


class TestGuards:
    async def test_unknown_repository(self, env):
        with pytest.raises(UnknownResourceError):
            await env["use_cases"].build_context_pack(uuid4(), "task")

    async def test_unsynced_repository_rejected(self, env):
        repo = await seed_repo(env, synced=False)
        with pytest.raises(RepositoryNotSyncedError):
            await env["use_cases"].build_context_pack(repo.id, "task")
        with pytest.raises(RepositoryNotSyncedError):
            await env["use_cases"].ask(repo.id, "question")
        with pytest.raises(RepositoryNotSyncedError):
            await env["use_cases"].search_docs(repo.id, "query")


class TestBuildContextPack:
    async def test_pack_combines_semantic_and_lexical(self, env):
        repo = await seed_repo(env)
        env["embeddings"].matches = [doc_match()]
        await env["issues"].save_many(
            [
                Issue(
                    id=uuid4(), repository_id=repo.id, github_issue_id=1, number=42,
                    title="Add OpenCL backend", body=None, state=IssueState.OPEN,
                    author="alice", created_at=NOW,
                ),
                Issue(
                    id=uuid4(), repository_id=repo.id, github_issue_id=2, number=43,
                    title="Fix docs typo", body=None, state=IssueState.OPEN,
                    author="alice", created_at=NOW,
                ),
            ]
        )
        await env["prs"].save_many(
            [
                PullRequest(
                    id=uuid4(), repository_id=repo.id, github_pr_id=3, number=61,
                    title="Refactor GPU backend abstraction", body=None,
                    state=PullRequestState.MERGED, merged=True, author="bob",
                    created_at=NOW,
                )
            ]
        )
        await env["openspec"].save(
            OpenSpecChange(
                id=uuid4(), repository_id=repo.id, change_id="add-gpu-backend",
                path="openspec/changes/add-gpu-backend", status=OpenSpecStatus.ACTIVE,
                proposal="GPU backend for OpenCL and Metal",
            )
        )

        pack = await env["use_cases"].build_context_pack(repo.id, "Implement OpenCL backend")

        assert pack.relevant_docs[0].path == "docs/gpu-backend.md"
        assert [i.number for i in pack.relevant_issues] == [42]  # typo issue filtered out
        assert [p.number for p in pack.relevant_pull_requests] == [61]
        assert pack.relevant_openspec_changes[0].change_id == "add-gpu-backend"
        assert "matforge" in pack.repository_summary
        assert any("add-gpu-backend" in r for r in pack.risks)  # active change flagged
        assert pack.suggested_next_steps

    async def test_docs_only_mode_excludes_issue_categories(self, env):
        repo = await seed_repo(env, mode=IndexingMode.DOCS_ONLY)
        env["embeddings"].matches = [doc_match()]
        pack = await env["use_cases"].build_context_pack(repo.id, "anything docs")
        assert pack.relevant_issues == []
        assert pack.relevant_pull_requests == []
        assert set(pack.excluded_categories) == {
            "issues", "pull_requests", "files", "source_code"
        }
        assert any("not indexed" in r for r in pack.risks)

    async def test_code_metadata_mode_includes_files(self, env):
        repo = await seed_repo(env, mode=IndexingMode.CODE_METADATA)
        env["embeddings"].matches = [doc_match()]
        await env["files"].replace_tree(
            repo.id,
            [
                SourceFile(
                    id=uuid4(), repository_id=repo.id, path="src/backend/gpu/cuda_backend.cpp",
                    extension="cpp", language="C++", size_bytes=10, sha="s",
                ),
                SourceFile(
                    id=uuid4(), repository_id=repo.id, path="assets/logo.png",
                    extension="png", language=None, size_bytes=10, sha="s2", is_binary=True,
                ),
            ],
        )
        pack = await env["use_cases"].build_context_pack(repo.id, "gpu backend cuda")
        assert [f.path for f in pack.relevant_files] == ["src/backend/gpu/cuda_backend.cpp"]

    async def test_cache_hit_for_identical_request(self, env):
        repo = await seed_repo(env)
        env["embeddings"].matches = [doc_match()]
        first = await env["use_cases"].build_context_pack(repo.id, "Implement OpenCL backend")
        second = await env["use_cases"].build_context_pack(repo.id, "implement opencl BACKEND")
        assert second.id == first.id  # served from cache
        assert len(env["packs"].saved) == 1

    async def test_new_sync_invalidates_cache(self, env):
        repo = await seed_repo(env)
        env["embeddings"].matches = [doc_match()]
        first = await env["use_cases"].build_context_pack(repo.id, "task")
        repo.last_synced_at = datetime(2026, 7, 8, tzinfo=UTC)
        await env["repositories"].save(repo)
        second = await env["use_cases"].build_context_pack(repo.id, "task")
        assert second.id != first.id


class TestAsk:
    async def test_grounded_answer_with_citations(self, env):
        repo = await seed_repo(env)
        env["embeddings"].matches = [doc_match(score=0.8), doc_match("README.md", 0.5)]
        result = await env["use_cases"].ask(repo.id, "how does the gpu backend work?")
        assert result["grounded"] is True
        assert [s["path"] for s in result["sources"]] == ["docs/gpu-backend.md", "README.md"]
        _question, blocks = env["answerer"].calls[0]
        assert blocks[0].startswith("[docs/gpu-backend.md]")

    async def test_insufficient_context_refuses(self, env):
        repo = await seed_repo(env)
        env["embeddings"].matches = [doc_match(score=0.05)]  # below threshold
        result = await env["use_cases"].ask(repo.id, "what is the billing model?")
        assert result["grounded"] is False
        assert result["sources"] == []
        assert "does not cover" in result["answer"]
        assert "issues" in result["answer"]  # lists indexed content types
        assert env["answerer"].calls == []  # LLM never called


class TestAskDeduplicatesSources:
    async def test_repeated_document_cited_once(self, env):
        repo = await seed_repo(env)
        # Two chunks of the same document + one of another
        env["embeddings"].matches = [
            doc_match("docs/2fa.md", 0.8),
            doc_match("docs/2fa.md", 0.6),
            doc_match("README.md", 0.5),
        ]
        result = await env["use_cases"].ask(repo.id, "how does 2fa work?")
        paths = [s["path"] for s in result["sources"]]
        assert paths == ["docs/2fa.md", "README.md"]  # deduped, order preserved
        assert result["sources"][0]["score"] == 0.8  # kept the higher score


class TestContextPackSourceChunks:
    async def test_code_mode_pack_includes_source_chunks(self, env):
        from app.domain.ports.infra_ports import CodeChunkMatch

        repo = await seed_repo(env, mode=IndexingMode.CODE_CONTEXT)
        env["embeddings"].matches = [doc_match()]
        env["embeddings"].code_matches = [
            CodeChunkMatch(
                chunk_id=uuid4(), file_id=uuid4(), path="src/gpu.cpp",
                symbol_name="dispatch", chunk_type="function",
                start_line=1, end_line=5, excerpt="void dispatch()", score=0.8,
            )
        ]
        pack = await env["use_cases"].build_context_pack(repo.id, "dispatch kernels")
        assert pack.source_chunks[0].symbol_name == "dispatch"
        assert "source_code" not in pack.excluded_categories

    async def test_non_code_mode_excludes_source(self, env):
        repo = await seed_repo(env, mode=IndexingMode.PROJECT_INTELLIGENCE)
        env["embeddings"].matches = [doc_match()]
        pack = await env["use_cases"].build_context_pack(repo.id, "anything")
        assert pack.source_chunks == []
        assert "source_code" in pack.excluded_categories
