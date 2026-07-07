"""Integration tests for the pgvector embedding store (real Postgres, fake OpenAI)."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.infrastructure.persistence.repositories.connections import PostgresConnectionRepository
from app.infrastructure.persistence.repositories.documents import PostgresDocumentRepository
from app.infrastructure.persistence.repositories.repositories import PostgresRepositoryRepository
from app.infrastructure.vector.pgvector_store import PgVectorEmbeddingStore
from tests.integration.persistence.test_repositories import make_connection, make_repo

NOW = datetime(2026, 7, 7, tzinfo=UTC)
DIMS = 1536

# Deterministic "embeddings": axis-aligned unit vectors per known text
_KNOWN = {
    "auth docs": 0,
    "deploy docs": 1,
    "how is authentication implemented": 0,  # same axis as "auth docs"
}


def fake_vector(text: str) -> list[float]:
    vector = [0.0] * DIMS
    vector[_KNOWN.get(text, 2)] = 1.0
    return vector


class FakeOpenAI:
    def __init__(self):
        self.embeddings = SimpleNamespace(create=self._create)
        self.calls = 0

    async def _create(self, model, input, dimensions):
        self.calls += 1
        return SimpleNamespace(
            data=[SimpleNamespace(embedding=fake_vector(t)) for t in input]
        )


@pytest.fixture
async def seeded(session_factory):
    connection = make_connection()
    await PostgresConnectionRepository(session_factory).save(connection)
    repo = make_repo(connection.id)
    await PostgresRepositoryRepository(session_factory).save(repo)

    from app.domain.entities.document import Document
    from app.domain.value_objects.enums import DocumentType

    docs = {}
    for path, title in [("docs/auth.md", "Auth"), ("docs/deploy.md", "Deploy")]:
        doc = Document(
            id=uuid4(),
            repository_id=repo.id,
            path=path,
            type=DocumentType.DOCS,
            title=title,
            content="...",
            content_hash=path,
            last_commit_sha=None,
            captured_at=NOW,
        )
        await PostgresDocumentRepository(session_factory).save(doc)
        docs[path] = doc
    return repo, docs


async def test_embed_and_search_ranks_by_similarity(session_factory, seeded):
    repo, docs = seeded
    store = PgVectorEmbeddingStore(session_factory, openai_client=FakeOpenAI())

    await store.embed_document(docs["docs/auth.md"].id, repo.id, ["auth docs"])
    await store.embed_document(docs["docs/deploy.md"].id, repo.id, ["deploy docs"])

    matches = await store.search(repo.id, "how is authentication implemented", limit=2)
    assert matches[0].path == "docs/auth.md"
    assert matches[0].score > matches[1].score
    assert matches[0].excerpt == "auth docs"


async def test_reembed_replaces_chunks(session_factory, seeded):
    repo, docs = seeded
    store = PgVectorEmbeddingStore(session_factory, openai_client=FakeOpenAI())
    doc_id = docs["docs/auth.md"].id

    await store.embed_document(doc_id, repo.id, ["auth docs", "deploy docs"])
    await store.embed_document(doc_id, repo.id, ["auth docs"])  # replaces both

    matches = await store.search(repo.id, "auth docs", limit=10)
    assert len([m for m in matches if m.document_id == doc_id]) == 1


async def test_delete_document_removes_chunks(session_factory, seeded):
    repo, docs = seeded
    store = PgVectorEmbeddingStore(session_factory, openai_client=FakeOpenAI())
    doc_id = docs["docs/auth.md"].id
    await store.embed_document(doc_id, repo.id, ["auth docs"])
    await store.delete_document(doc_id)
    assert await store.search(repo.id, "auth docs", limit=10) == []


async def test_empty_chunks_no_api_call(session_factory, seeded):
    repo, docs = seeded
    fake = FakeOpenAI()
    store = PgVectorEmbeddingStore(session_factory, openai_client=fake)
    assert await store.embed_document(docs["docs/auth.md"].id, repo.id, []) == 0
    assert fake.calls == 0
