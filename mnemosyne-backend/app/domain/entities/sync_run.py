"""Scheduled-run history entry (spec: repository-sync, rest-api)."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class SyncRun:
    id: UUID
    trigger: str  # "scheduler"
    started_at: datetime
    finished_at: datetime
    discovered: int
    newly_enabled: int
    skipped_archived: int
    enqueued: int
    skipped: int
    failed: int
