"""Repository entity: discovered GitHub repository + indexing selection state."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.value_objects.enums import IndexingMode, RepositoryVisibility
from app.domain.value_objects.full_name import RepositoryFullName


@dataclass(slots=True)
class Repository:
    id: UUID
    connection_id: UUID
    github_id: int
    full_name: RepositoryFullName
    description: str | None
    visibility: RepositoryVisibility
    default_branch: str
    primary_language: str | None
    archived: bool
    github_updated_at: datetime | None
    enabled: bool = False
    indexing_mode: IndexingMode = IndexingMode.DOCS_ONLY
    last_synced_at: datetime | None = None

    @property
    def owner(self) -> str:
        return self.full_name.owner

    @property
    def name(self) -> str:
        return self.full_name.name

    @property
    def synced(self) -> bool:
        return self.last_synced_at is not None

    def enable(self, mode: IndexingMode) -> None:
        self.enabled = True
        self.indexing_mode = mode

    def disable(self) -> None:
        self.enabled = False
