"""Queue, object-storage, embedding, and LLM ports."""

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID


class QueuePort(Protocol):
    async def enqueue(self, job_name: str, payload: dict[str, Any]) -> None: ...


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


class EmbeddingPort(Protocol):
    async def embed_document(
        self, document_id: UUID, repository_id: UUID, chunks: list[str]
    ) -> int: ...

    async def delete_document(self, document_id: UUID) -> None: ...

    async def search(
        self, repository_id: UUID, query: str, *, limit: int = 8
    ) -> list[ChunkMatch]: ...


class AnswerPort(Protocol):
    """LLM answer synthesis for ask_repository_question (design OQ1)."""

    async def answer(self, question: str, context_blocks: list[str]) -> str: ...
