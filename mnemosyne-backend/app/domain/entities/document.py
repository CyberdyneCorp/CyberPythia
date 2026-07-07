"""Captured documentation file."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.value_objects.enums import DocumentType, EmbeddingStatus


@dataclass(slots=True)
class Document:
    id: UUID
    repository_id: UUID
    path: str
    type: DocumentType
    title: str
    content: str | None  # None when quarantined (spec: repository-sync, secret quarantine)
    content_hash: str
    last_commit_sha: str | None
    quarantined: bool = False
    embedding_status: EmbeddingStatus = EmbeddingStatus.PENDING
    captured_at: datetime | None = None

    @property
    def embeddable(self) -> bool:
        return not self.quarantined and self.content is not None
