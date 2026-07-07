"""File-tree entry captured for a repository (mode: code_metadata)."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(slots=True)
class SourceFile:
    id: UUID
    repository_id: UUID
    path: str
    extension: str | None
    language: str | None
    size_bytes: int
    sha: str
    is_binary: bool = False
    is_important: bool = False
    important_kind: str | None = None  # e.g. "dependency_manifest", "ci_workflow"
    last_seen_at: datetime | None = None
