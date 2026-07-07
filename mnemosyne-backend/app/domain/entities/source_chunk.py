"""Symbol-bounded chunk of a source file (spec: code-context)."""

from dataclasses import dataclass
from uuid import UUID

from app.domain.value_objects.enums import ChunkType


@dataclass(slots=True)
class SourceChunk:
    id: UUID
    file_id: UUID
    repository_id: UUID
    chunk_type: ChunkType
    symbol_name: str | None
    start_line: int
    end_line: int
    content: str
    content_hash: str
    embedded: bool = False
