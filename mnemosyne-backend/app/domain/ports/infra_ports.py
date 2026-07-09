"""Queue, object-storage, embedding, and LLM ports."""

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID


class QueuePort(Protocol):
    async def enqueue(
        self, job_name: str, payload: dict[str, Any], *, defer_seconds: float = 0.0
    ) -> None: ...


class SyncLockPort(Protocol):
    async def acquire(self, repository_id: UUID) -> bool: ...

    async def release(self, repository_id: UUID) -> None: ...

    async def is_locked(self, repository_id: UUID) -> bool: ...


class ObjectStoragePort(Protocol):
    async def put_json(self, key: str, payload: Any) -> None: ...

    async def get_json(self, key: str) -> Any: ...


@dataclass(frozen=True, slots=True)
class ChunkMatch:
    document_id: UUID
    path: str
    title: str
    doc_type: str
    excerpt: str
    score: float
    repository_id: UUID | None = None  # set by global search; None for per-repo


@dataclass(frozen=True, slots=True)
class CodeChunkMatch:
    chunk_id: UUID
    file_id: UUID
    path: str
    symbol_name: str | None
    chunk_type: str
    start_line: int
    end_line: int
    excerpt: str
    score: float
    repository_id: UUID | None = None  # set by global search; None for per-repo


@dataclass(frozen=True, slots=True)
class EmbeddableChunk:
    """A source chunk ready to embed (identity + text)."""

    chunk_id: UUID
    text: str


class EmbeddingPort(Protocol):
    async def embed_document(
        self, document_id: UUID, repository_id: UUID, chunks: list[str]
    ) -> int: ...

    async def delete_document(self, document_id: UUID) -> None: ...

    async def search(
        self, repository_id: UUID, query: str, *, limit: int = 8
    ) -> list[ChunkMatch]: ...

    async def search_global(
        self, query: str, *, repository_ids: list[UUID] | None = None, limit: int = 8
    ) -> list[ChunkMatch]: ...

    async def embed_source_chunks(
        self, repository_id: UUID, chunks: list[EmbeddableChunk]
    ) -> int: ...

    async def search_code(
        self, repository_id: UUID, query: str, *, limit: int = 8
    ) -> list[CodeChunkMatch]: ...

    async def search_code_global(
        self, query: str, *, repository_ids: list[UUID] | None = None, limit: int = 8
    ) -> list[CodeChunkMatch]: ...


class AnswerPort(Protocol):
    """LLM answer synthesis for ask_repository_question (design OQ1)."""

    async def answer(self, question: str, context_blocks: list[str]) -> str: ...
