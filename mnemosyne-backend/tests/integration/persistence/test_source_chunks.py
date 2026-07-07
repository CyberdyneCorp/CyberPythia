"""Integration tests for source-file content + source-chunk adapters (real Postgres)."""

from uuid import uuid4

from app.domain.entities.source_chunk import SourceChunk
from app.domain.entities.source_file import SourceFile
from app.domain.value_objects.enums import ChunkType
from app.infrastructure.persistence.repositories.misc import (
    PostgresFileRepository,
    PostgresSourceChunkRepository,
)
from tests.integration.persistence.test_repositories import seed_repo


async def make_file(session_factory, repo_id, path="src/app.py") -> SourceFile:
    files = PostgresFileRepository(session_factory)
    f = SourceFile(
        id=uuid4(),
        repository_id=repo_id,
        path=path,
        extension="py",
        language="Python",
        size_bytes=100,
        sha="sha1",
    )
    await files.replace_tree(repo_id, [f])
    return (await files.list_by_repository(repo_id))[0]


class TestFileContent:
    async def test_save_and_read_content(self, session_factory):
        repo = await seed_repo(session_factory)
        f = await make_file(session_factory, repo.id)
        files = PostgresFileRepository(session_factory)

        f.content = "print('hi')"
        f.content_captured = True
        f.content_hash = "h1"
        await files.save_content(f)

        loaded = await files.get(f.id)
        assert loaded.content == "print('hi')"
        assert loaded.content_captured and loaded.content_hash == "h1"
        assert not loaded.quarantined

    async def test_quarantine_flag(self, session_factory):
        repo = await seed_repo(session_factory)
        f = await make_file(session_factory, repo.id)
        files = PostgresFileRepository(session_factory)
        f.quarantined = True
        f.content = None
        f.content_captured = False
        await files.save_content(f)
        assert (await files.get_by_path(repo.id, f.path)).quarantined

    async def test_replace_tree_resets_content_columns(self, session_factory):
        repo = await seed_repo(session_factory)
        f = await make_file(session_factory, repo.id)
        files = PostgresFileRepository(session_factory)
        f.content = "x"
        f.content_captured = True
        await files.save_content(f)
        # a fresh tree (new sync) drops old rows
        await files.replace_tree(repo.id, [])
        assert await files.list_by_repository(repo.id) == []


class TestSourceChunks:
    async def test_replace_and_list(self, session_factory):
        repo = await seed_repo(session_factory)
        f = await make_file(session_factory, repo.id)
        chunks_repo = PostgresSourceChunkRepository(session_factory)

        chunks = [
            SourceChunk(
                id=uuid4(), file_id=f.id, repository_id=repo.id,
                chunk_type=ChunkType.FUNCTION, symbol_name="run",
                start_line=1, end_line=5, content="def run(): ...", content_hash="c1",
            ),
            SourceChunk(
                id=uuid4(), file_id=f.id, repository_id=repo.id,
                chunk_type=ChunkType.CLASS, symbol_name="Backend",
                start_line=7, end_line=20, content="class Backend: ...", content_hash="c2",
            ),
        ]
        await chunks_repo.replace_for_file(f.id, chunks)
        listed = await chunks_repo.list_by_repository(repo.id)
        assert [c.symbol_name for c in listed] == ["run", "Backend"]  # ordered by start_line

    async def test_replace_is_idempotent_per_file(self, session_factory):
        repo = await seed_repo(session_factory)
        f = await make_file(session_factory, repo.id)
        chunks_repo = PostgresSourceChunkRepository(session_factory)
        first = [
            SourceChunk(id=uuid4(), file_id=f.id, repository_id=repo.id,
                        chunk_type=ChunkType.WINDOW, symbol_name=None,
                        start_line=1, end_line=3, content="old", content_hash="o")
        ]
        await chunks_repo.replace_for_file(f.id, first)
        second = [
            SourceChunk(id=uuid4(), file_id=f.id, repository_id=repo.id,
                        chunk_type=ChunkType.FUNCTION, symbol_name="run",
                        start_line=1, end_line=3, content="new", content_hash="n")
        ]
        await chunks_repo.replace_for_file(f.id, second)
        listed = await chunks_repo.list_by_repository(repo.id)
        assert len(listed) == 1 and listed[0].content == "new"

    async def test_get_by_symbol(self, session_factory):
        repo = await seed_repo(session_factory)
        f = await make_file(session_factory, repo.id)
        chunks_repo = PostgresSourceChunkRepository(session_factory)
        await chunks_repo.replace_for_file(
            f.id,
            [
                SourceChunk(id=uuid4(), file_id=f.id, repository_id=repo.id,
                            chunk_type=ChunkType.FUNCTION, symbol_name="dispatch",
                            start_line=1, end_line=5, content="...", content_hash="c"),
            ],
        )
        found = await chunks_repo.get_by_symbol(repo.id, "dispatch")
        assert len(found) == 1 and found[0].symbol_name == "dispatch"
        assert await chunks_repo.get_by_symbol(repo.id, "nope") == []

    async def test_delete_for_file(self, session_factory):
        repo = await seed_repo(session_factory)
        f = await make_file(session_factory, repo.id)
        chunks_repo = PostgresSourceChunkRepository(session_factory)
        await chunks_repo.replace_for_file(
            f.id,
            [SourceChunk(id=uuid4(), file_id=f.id, repository_id=repo.id,
                         chunk_type=ChunkType.WINDOW, symbol_name=None,
                         start_line=1, end_line=2, content="x", content_hash="c")],
        )
        await chunks_repo.delete_for_file(f.id)
        assert await chunks_repo.list_by_repository(repo.id) == []
