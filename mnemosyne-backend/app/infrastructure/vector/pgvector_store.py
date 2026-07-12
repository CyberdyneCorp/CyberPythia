"""EmbeddingPort adapter: OpenAI embeddings + pgvector storage (design D7)."""

from uuid import UUID, uuid4

from openai import AsyncOpenAI, BadRequestError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.domain.ports.infra_ports import ChunkMatch, CodeChunkMatch, EmbeddableChunk
from app.infrastructure.persistence.models import (
    DocumentChunkRow,
    DocumentRow,
    SourceChunkRow,
    SourceFileRow,
)

EXCERPT_CHARS = 400
# Bulletproof retry cap: text-embedding-3 allows <= 8192 tokens and a token is
# always >= 1 character, so <= 8000 characters can never exceed the token limit.
_HARD_INPUT_CHARS = 8000


class PgVectorEmbeddingStore:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        openai_client: AsyncOpenAI | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._settings = get_settings()
        self._openai = openai_client

    def _client(self) -> AsyncOpenAI:
        if self._openai is None:
            self._openai = AsyncOpenAI(api_key=self._settings.openai_api_key)
        return self._openai

    async def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not self._settings.openai_api_key and self._openai is None:
            # Degraded mode (no API key): deterministic bag-of-words hashing.
            # Weak but functional similarity for dev/BDD stacks.
            return [_hash_embedding(t, self._settings.embedding_dimensions) for t in texts]
        cap = self._settings.embedding_max_input_chars
        try:
            return await self._create_embeddings([t[:cap] for t in texts])
        except BadRequestError as exc:
            # A pathologically token-dense chunk can still exceed 8192 tokens
            # under the soft cap. A token is always >= 1 char, so truncating to
            # the token limit in characters is a hard guarantee. Retry once.
            if "maximum input length" not in str(exc):
                raise
            hard = min(cap, _HARD_INPUT_CHARS)
            return await self._create_embeddings([t[:hard] for t in texts])

    async def _create_embeddings(self, texts: list[str]) -> list[list[float]]:
        response = await self._client().embeddings.create(
            model=self._settings.embedding_model,
            input=texts,
            dimensions=self._settings.embedding_dimensions,
        )
        return [item.embedding for item in response.data]

    async def embed_document(
        self, document_id: UUID, repository_id: UUID, chunks: list[str]
    ) -> int:
        if not chunks:
            return 0
        vectors = await self._embed_texts(chunks)
        async with self._session_factory() as session, session.begin():
            await session.execute(
                delete(DocumentChunkRow).where(DocumentChunkRow.document_id == document_id)
            )
            for index, (content, vector) in enumerate(zip(chunks, vectors, strict=True)):
                session.add(
                    DocumentChunkRow(
                        id=uuid4(),
                        document_id=document_id,
                        repository_id=repository_id,
                        chunk_index=index,
                        content=content,
                        embedding=vector,
                    )
                )
        return len(chunks)

    async def delete_document(self, document_id: UUID) -> None:
        async with self._session_factory() as session, session.begin():
            await session.execute(
                delete(DocumentChunkRow).where(DocumentChunkRow.document_id == document_id)
            )

    async def search(
        self, repository_id: UUID, query: str, *, limit: int = 8
    ) -> list[ChunkMatch]:
        (query_vector,) = await self._embed_texts([query])
        async with self._session_factory() as session:
            distance = DocumentChunkRow.embedding.cosine_distance(query_vector)
            rows = (
                await session.execute(
                    select(DocumentChunkRow, DocumentRow, distance.label("distance"))
                    .join(DocumentRow, DocumentRow.id == DocumentChunkRow.document_id)
                    .where(DocumentChunkRow.repository_id == repository_id)
                    .order_by(distance)
                    .limit(limit)
                )
            ).all()
        return [
            ChunkMatch(
                document_id=chunk.document_id,
                path=doc.path,
                title=doc.title,
                doc_type=doc.type,
                excerpt=chunk.content[:EXCERPT_CHARS],
                score=max(0.0, 1.0 - float(dist)),  # cosine distance -> similarity
            )
            for chunk, doc, dist in rows
        ]

    async def search_global(
        self, query: str, *, repository_ids: list[UUID] | None = None, limit: int = 8
    ) -> list[ChunkMatch]:
        (query_vector,) = await self._embed_texts([query])
        async with self._session_factory() as session:
            distance = DocumentChunkRow.embedding.cosine_distance(query_vector)
            stmt = (
                select(DocumentChunkRow, DocumentRow, distance.label("distance"))
                .join(DocumentRow, DocumentRow.id == DocumentChunkRow.document_id)
            )
            if repository_ids is not None:
                stmt = stmt.where(DocumentChunkRow.repository_id.in_(repository_ids))
            rows = (await session.execute(stmt.order_by(distance).limit(limit))).all()
        return [
            ChunkMatch(
                document_id=chunk.document_id,
                path=doc.path,
                title=doc.title,
                doc_type=doc.type,
                excerpt=chunk.content[:EXCERPT_CHARS],
                score=max(0.0, 1.0 - float(dist)),
                repository_id=chunk.repository_id,
            )
            for chunk, doc, dist in rows
        ]

    async def embed_source_chunks(
        self, repository_id: UUID, chunks: list[EmbeddableChunk]
    ) -> int:
        if not chunks:
            return 0
        vectors = await self._embed_texts([c.text for c in chunks])
        async with self._session_factory() as session, session.begin():
            for chunk, vector in zip(chunks, vectors, strict=True):
                row = await session.get(SourceChunkRow, chunk.chunk_id)
                if row is not None:
                    row.embedding = vector
        return len(chunks)

    async def search_code(
        self, repository_id: UUID, query: str, *, limit: int = 8
    ) -> list[CodeChunkMatch]:
        (query_vector,) = await self._embed_texts([query])
        async with self._session_factory() as session:
            distance = SourceChunkRow.embedding.cosine_distance(query_vector)
            rows = (
                await session.execute(
                    select(SourceChunkRow, SourceFileRow, distance.label("distance"))
                    .join(SourceFileRow, SourceFileRow.id == SourceChunkRow.file_id)
                    .where(
                        SourceChunkRow.repository_id == repository_id,
                        SourceChunkRow.embedding.is_not(None),
                    )
                    .order_by(distance)
                    .limit(limit)
                )
            ).all()
        return [
            CodeChunkMatch(
                chunk_id=chunk.id,
                file_id=chunk.file_id,
                path=file.path,
                symbol_name=chunk.symbol_name,
                chunk_type=chunk.chunk_type,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                excerpt=chunk.content[:EXCERPT_CHARS],
                score=max(0.0, 1.0 - float(dist)),
            )
            for chunk, file, dist in rows
        ]

    async def search_code_global(
        self, query: str, *, repository_ids: list[UUID] | None = None, limit: int = 8
    ) -> list[CodeChunkMatch]:
        (query_vector,) = await self._embed_texts([query])
        async with self._session_factory() as session:
            distance = SourceChunkRow.embedding.cosine_distance(query_vector)
            stmt = (
                select(SourceChunkRow, SourceFileRow, distance.label("distance"))
                .join(SourceFileRow, SourceFileRow.id == SourceChunkRow.file_id)
                .where(SourceChunkRow.embedding.is_not(None))
            )
            if repository_ids is not None:
                stmt = stmt.where(SourceChunkRow.repository_id.in_(repository_ids))
            rows = (await session.execute(stmt.order_by(distance).limit(limit))).all()
        return [
            CodeChunkMatch(
                chunk_id=chunk.id,
                file_id=chunk.file_id,
                path=file.path,
                symbol_name=chunk.symbol_name,
                chunk_type=chunk.chunk_type,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                excerpt=chunk.content[:EXCERPT_CHARS],
                score=max(0.0, 1.0 - float(dist)),
                repository_id=chunk.repository_id,
            )
            for chunk, file, dist in rows
        ]


def _hash_embedding(text: str, dimensions: int) -> list[float]:
    import hashlib
    import math
    import re

    vector = [0.0] * dimensions
    for token in re.findall(r"[a-z0-9]{2,}", text.lower()):
        # blake2b (not md5, CWE-327): only a non-cryptographic bucketing of tokens
        # for the OpenAI-unavailable degraded-mode fallback vector.
        digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        vector[index] += 1.0
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]
