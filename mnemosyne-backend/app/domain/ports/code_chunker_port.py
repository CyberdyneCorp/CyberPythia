"""Code chunking port (design D2). The default adapter is the pure-Python
heuristic service in domain/services; a tree-sitter adapter can replace it."""

from dataclasses import dataclass
from typing import Protocol

from app.domain.value_objects.enums import ChunkType


@dataclass(frozen=True, slots=True)
class CodeChunk:
    chunk_type: ChunkType
    symbol_name: str | None
    start_line: int  # 1-based, inclusive
    end_line: int  # 1-based, inclusive
    content: str


class CodeChunkerPort(Protocol):
    def chunk(self, path: str, content: str, language: str | None) -> list[CodeChunk]:
        """Split source into symbol-bounded (or windowed) chunks. Deterministic."""
        ...
