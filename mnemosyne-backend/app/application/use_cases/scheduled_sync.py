"""Scheduled daily full sync of all enabled repositories (spec: repository-sync).

Runs in the worker via an arq cron. Fans out one enqueue per enabled repository
through the existing ``trigger_sync``, which already respects the per-repo lock and
the pending/running guard — so a repo already syncing is skipped, and one repo
failing does not stop the rest.
"""

import logging
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.application.errors import ApplicationError, SyncAlreadyRunningError
from app.domain.entities.repository import Repository

logger = logging.getLogger(__name__)


class _Repositories(Protocol):
    async def list_all(self, *, enabled_only: bool = False) -> list[Repository]: ...


class _Trigger(Protocol):
    async def trigger_sync(
        self, repository_id: UUID, *, triggered_by: str, defer_seconds: float = 0.0
    ) -> object: ...


@dataclass(frozen=True, slots=True)
class ScheduledSyncSummary:
    enqueued: int
    skipped: int
    failed: int


class ScheduledSyncService:
    def __init__(
        self,
        repositories: _Repositories,
        repository_use_cases: _Trigger,
        *,
        stagger_seconds: float = 0.0,
    ) -> None:
        self._repositories = repositories
        self._use_cases = repository_use_cases
        self._stagger_seconds = stagger_seconds

    async def run(self) -> ScheduledSyncSummary:
        repositories = await self._repositories.list_all(enabled_only=True)
        enqueued = skipped = failed = 0
        for index, repo in enumerate(repositories):
            try:
                await self._use_cases.trigger_sync(
                    repo.id,
                    triggered_by="scheduler",
                    defer_seconds=index * self._stagger_seconds,
                )
                enqueued += 1
            except SyncAlreadyRunningError:
                skipped += 1
            except ApplicationError:
                logger.warning("scheduled sync: skipping %s (not enqueuable)", repo.full_name)
                skipped += 1
            except Exception:
                logger.exception("scheduled sync: failed to enqueue %s", repo.full_name)
                failed += 1
        logger.info(
            "scheduled full sync: enqueued=%d skipped=%d failed=%d over %d enabled repos",
            enqueued,
            skipped,
            failed,
            len(repositories),
        )
        return ScheduledSyncSummary(enqueued=enqueued, skipped=skipped, failed=failed)
