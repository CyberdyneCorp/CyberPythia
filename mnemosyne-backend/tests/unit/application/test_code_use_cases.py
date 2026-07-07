"""Unit tests for code search, symbols, file content, related files (spec: code-context)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.application.audit import AuditService
from app.application.errors import (
    ContentUnavailableError,
    RepositoryNotSyncedError,
    SourceNotIndexedError,
    UnknownResourceError,
)
from app.application.use_cases.code import CodeUseCases
from app.domain.entities.repository import Repository
from app.domain.entities.source_chunk import SourceChunk
from app.domain.entities.source_file import SourceFile
from app.domain.ports.infra_ports import CodeChunkMatch
from app.domain.value_objects.enums import ChunkType, IndexingMode, RepositoryVisibility
from app.domain.value_objects.full_name import RepositoryFullName
from app.domain.value_objects.identity import CallerIdentity
from tests.unit.application.fakes import (
    FakeFilePort,
    FakeRepositoryPort,
    FakeSourceChunkPort,
)
from tests.unit.interfaces.conftest import FakeAuditPort

NOW = datetime(2026, 7, 7, tzinfo=UTC)


class FakeCodeEmbeddings:
    def __init__(self):
        self.matches: list[CodeChunkMatch] = []

    async def embed_document(self, *a, **k):
        return 0

    async def delete_document(self, *a, **k):
        pass

    async def search(self, *a, **k):
        return []

    async def embed_source_chunks(self, repository_id, chunks):
        return len(chunks)

    async def search_code(self, repository_id, query, *, limit=8):
        return self.matches[:limit]


def make_repo(mode=IndexingMode.CODE_CONTEXT, synced=True):
    return Repository(
        id=uuid4(), connection_id=uuid4(), github_id=1,
        full_name=RepositoryFullName("cyberdyne/matforge"), description="d",
        visibility=RepositoryVisibility.PRIVATE, default_branch="main",
        primary_language="C++", archived=False, github_updated_at=NOW,
        enabled=True, indexing_mode=mode, last_synced_at=NOW if synced else None,
    )


def make_file(repo_id, path="src/gpu.cpp", **kw):
    defaults = dict(
        id=uuid4(), repository_id=repo_id, path=path, extension="cpp",
        language="C++", size_bytes=100, sha="s",
    )
    defaults.update(kw)
    return SourceFile(**defaults)


@pytest.fixture
def env():
    repositories = FakeRepositoryPort()
    files = FakeFilePort()
    chunks = FakeSourceChunkPort()
    embeddings = FakeCodeEmbeddings()
    audit_port = FakeAuditPort()
    use_cases = CodeUseCases(
        repositories, files, chunks, embeddings, AuditService(audit_port)
    )
    return {
        "use_cases": use_cases, "repositories": repositories, "files": files,
        "chunks": chunks, "embeddings": embeddings, "audit_port": audit_port,
    }


async def seed(env, mode=IndexingMode.CODE_CONTEXT, synced=True):
    repo = make_repo(mode, synced)
    await env["repositories"].save(repo)
    return repo


class TestGuards:
    async def test_unknown_repository(self, env):
        with pytest.raises(UnknownResourceError):
            await env["use_cases"].search_code(uuid4(), "q")

    async def test_unsynced(self, env):
        repo = await seed(env, synced=False)
        with pytest.raises(RepositoryNotSyncedError):
            await env["use_cases"].search_code(repo.id, "q")

    async def test_non_code_mode_rejected(self, env):
        repo = await seed(env, mode=IndexingMode.CODE_METADATA)
        with pytest.raises(SourceNotIndexedError):
            await env["use_cases"].search_code(repo.id, "q")
        with pytest.raises(SourceNotIndexedError):
            await env["use_cases"].symbols(repo.id)


class TestCodeSearch:
    async def test_returns_matches(self, env):
        repo = await seed(env)
        env["embeddings"].matches = [
            CodeChunkMatch(
                chunk_id=uuid4(), file_id=uuid4(), path="src/gpu.cpp",
                symbol_name="dispatch", chunk_type="function",
                start_line=1, end_line=5, excerpt="void dispatch()", score=0.9,
            )
        ]
        matches = await env["use_cases"].search_code(repo.id, "dispatch kernels")
        assert matches[0].symbol_name == "dispatch"


class TestSymbols:
    async def test_list_and_filter(self, env):
        repo = await seed(env)
        f = make_file(repo.id)
        await env["files"].replace_tree(repo.id, [f])
        await env["chunks"].replace_for_file(
            f.id,
            [
                SourceChunk(id=uuid4(), file_id=f.id, repository_id=repo.id,
                            chunk_type=ChunkType.FUNCTION, symbol_name="dispatch",
                            start_line=1, end_line=5, content="...", content_hash="c"),
                SourceChunk(id=uuid4(), file_id=f.id, repository_id=repo.id,
                            chunk_type=ChunkType.WINDOW, symbol_name=None,
                            start_line=7, end_line=9, content="...", content_hash="d"),
            ],
        )
        allsyms = await env["use_cases"].symbols(repo.id)
        assert [s["symbol_name"] for s in allsyms] == ["dispatch"]  # window excluded
        one = await env["use_cases"].symbols(repo.id, "dispatch")
        assert len(one) == 1 and one[0]["chunk_type"] == "function"


class TestFileContent:
    async def test_captured_content_returned_and_audited(self, env):
        repo = await seed(env)
        f = make_file(repo.id, content="void dispatch(){}", content_captured=True,
                      content_hash="h")
        await env["files"].replace_tree(repo.id, [f])
        caller = CallerIdentity(subject="u1", entitlements=frozenset({"mnemosyne"}))
        result = await env["use_cases"].file_content(repo.id, f.id, caller)
        assert result["content"] == "void dispatch(){}"
        assert env["audit_port"].records[-1].operation == "code.file_content"

    async def test_quarantined_content_unavailable(self, env):
        repo = await seed(env)
        f = make_file(repo.id, quarantined=True, content=None, content_captured=False)
        await env["files"].replace_tree(repo.id, [f])
        with pytest.raises(ContentUnavailableError, match="quarantined"):
            await env["use_cases"].file_content(repo.id, f.id)

    async def test_uncaptured_content_unavailable(self, env):
        repo = await seed(env)
        f = make_file(repo.id, content=None, content_captured=False)
        await env["files"].replace_tree(repo.id, [f])
        with pytest.raises(ContentUnavailableError, match="not captured"):
            await env["use_cases"].file_content(repo.id, f.id)

    async def test_unknown_file(self, env):
        repo = await seed(env)
        with pytest.raises(UnknownResourceError):
            await env["use_cases"].file_content(repo.id, uuid4())


class TestRelatedFiles:
    async def test_imports_and_imported_by(self, env):
        repo = await seed(env)
        backend = make_file(repo.id, path="src/backend.py",
                            content="from gpu import dispatch\n", content_captured=True)
        gpu = make_file(repo.id, path="src/gpu.py",
                        content="def dispatch(): ...\n", content_captured=True)
        await env["files"].replace_tree(repo.id, [backend, gpu])
        related = await env["use_cases"].related_files(repo.id, backend.id)
        assert "src/gpu.py" in related["imports"]
        gpu_related = await env["use_cases"].related_files(repo.id, gpu.id)
        assert "src/backend.py" in gpu_related["imported_by"]


class TestExplainStructure:
    async def test_summary(self, env):
        repo = await seed(env)
        files = [
            make_file(repo.id, path="src/a.py", language="Python"),
            make_file(repo.id, path="pyproject.toml", language=None,
                      is_important=True, important_kind="dependency_manifest"),
        ]
        await env["files"].replace_tree(repo.id, files)
        result = await env["use_cases"].explain_structure(repo.id)
        assert result["file_count"] == 2
        assert result["languages"].get("Python") == 1
        assert any(i["kind"] == "dependency_manifest" for i in result["important_files"])

    async def test_structure_works_for_non_code_mode(self, env):
        # explain_structure is allowed below code_context (tree-only)
        repo = await seed(env, mode=IndexingMode.CODE_METADATA)
        await env["files"].replace_tree(repo.id, [make_file(repo.id)])
        result = await env["use_cases"].explain_structure(repo.id)
        assert result["key_symbols"] == []  # no code symbols in metadata mode
