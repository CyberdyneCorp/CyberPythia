"""Integration tests for source-chunk embedding + code search (real Postgres, fake OpenAI)."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.domain.entities.source_chunk import SourceChunk
from app.domain.entities.source_file import SourceFile
from app.domain.ports.infra_ports import EmbeddableChunk
from app.domain.value_objects.enums import ChunkType
from app.infrastructure.persistence.repositories.misc import (
    PostgresFileRepository,
    PostgresSourceChunkRepository,
)
from app.infrastructure.vector.pgvector_store import PgVectorEmbeddingStore
from tests.integration.persistence.test_repositories import seed_repo

DIMS = 1536
_AXIS = {"dispatch gpu kernels": 0, "parse config file": 1, "how are kernels dispatched": 0}


def fake_vector(text: str) -> list[float]:
    v = [0.0] * DIMS
    v[_AXIS.get(text, 2)] = 1.0
    return v


class FakeOpenAI:
    def __init__(self):
        self.embeddings = SimpleNamespace(create=self._create)

    async def _create(self, model, input, dimensions):
        return SimpleNamespace(data=[SimpleNamespace(embedding=fake_vector(t)) for t in input])


@pytest.fixture
async def seeded(session_factory):
    repo = await seed_repo(session_factory)
    files = PostgresFileRepository(session_factory)
    f = SourceFile(
        id=uuid4(), repository_id=repo.id, path="src/gpu.py", extension="py",
        language="Python", size_bytes=10, sha="s",
    )
    await files.replace_tree(repo.id, [f])
    f = (await files.list_by_repository(repo.id))[0]

    chunks = PostgresSourceChunkRepository(session_factory)
    dispatch = SourceChunk(
        id=uuid4(), file_id=f.id, repository_id=repo.id, chunk_type=ChunkType.FUNCTION,
        symbol_name="dispatch", start_line=1, end_line=5,
        content="def dispatch(): ...", content_hash="c1",
    )
    parse = SourceChunk(
        id=uuid4(), file_id=f.id, repository_id=repo.id, chunk_type=ChunkType.FUNCTION,
        symbol_name="parse", start_line=7, end_line=12,
        content="def parse(): ...", content_hash="c2",
    )
    await chunks.replace_for_file(f.id, [dispatch, parse])
    return repo, f, dispatch, parse


async def test_embed_and_code_search_ranks_by_similarity(session_factory, seeded):
    repo, f, dispatch, parse = seeded
    store = PgVectorEmbeddingStore(session_factory, openai_client=FakeOpenAI())

    await store.embed_source_chunks(
        repo.id,
        [
            EmbeddableChunk(chunk_id=dispatch.id, text="dispatch gpu kernels"),
            EmbeddableChunk(chunk_id=parse.id, text="parse config file"),
        ],
    )
    matches = await store.search_code(repo.id, "how are kernels dispatched", limit=2)
    assert matches[0].symbol_name == "dispatch"
    assert matches[0].path == "src/gpu.py"
    assert matches[0].chunk_type == "function"
    assert matches[0].score > matches[1].score


async def test_unembedded_chunks_excluded_from_code_search(session_factory, seeded):
    repo, f, dispatch, parse = seeded
    store = PgVectorEmbeddingStore(session_factory, openai_client=FakeOpenAI())
    # embed only one chunk
    await store.embed_source_chunks(
        repo.id, [EmbeddableChunk(chunk_id=dispatch.id, text="dispatch gpu kernels")]
    )
    matches = await store.search_code(repo.id, "anything", limit=10)
    assert [m.symbol_name for m in matches] == ["dispatch"]


async def test_empty_chunks_no_api_call(session_factory, seeded):
    repo = seeded[0]
    store = PgVectorEmbeddingStore(session_factory, openai_client=FakeOpenAI())
    assert await store.embed_source_chunks(repo.id, []) == 0
