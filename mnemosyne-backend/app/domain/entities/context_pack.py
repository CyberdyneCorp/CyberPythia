"""Context pack: curated task-specific context for an agent (spec: context-packs)."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.domain.value_objects.enums import IndexingMode


@dataclass(frozen=True, slots=True)
class DocRef:
    path: str
    title: str
    doc_type: str
    score: float
    excerpt: str | None = None


@dataclass(frozen=True, slots=True)
class OpenSpecRef:
    change_id: str
    path: str
    status: str
    score: float


@dataclass(frozen=True, slots=True)
class IssueRef:
    number: int
    title: str
    state: str
    score: float


@dataclass(frozen=True, slots=True)
class PullRequestRef:
    number: int
    title: str
    state: str
    score: float


@dataclass(frozen=True, slots=True)
class FileRef:
    path: str
    kind: str | None
    score: float


@dataclass(frozen=True, slots=True)
class SourceChunkRef:
    path: str
    symbol_name: str | None
    chunk_type: str
    start_line: int
    end_line: int
    score: float
    excerpt: str | None = None


@dataclass(slots=True)
class ContextPack:
    id: UUID
    repository_id: UUID
    query: str
    mode: IndexingMode
    repository_summary: str
    relevant_docs: list[DocRef] = field(default_factory=list)
    relevant_openspec_changes: list[OpenSpecRef] = field(default_factory=list)
    relevant_issues: list[IssueRef] = field(default_factory=list)
    relevant_pull_requests: list[PullRequestRef] = field(default_factory=list)
    relevant_files: list[FileRef] = field(default_factory=list)
    source_chunks: list[SourceChunkRef] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    suggested_next_steps: list[str] = field(default_factory=list)
    excluded_categories: list[str] = field(default_factory=list)  # mode-excluded content
    sync_timestamp: datetime | None = None
    created_at: datetime | None = None
