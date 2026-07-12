"""Scheduled daily full sync of all enabled repositories (spec: repository-sync).

Runs in the worker via an arq cron. Fans out one enqueue per enabled repository
through the existing ``trigger_sync``, which already respects the per-repo lock and
the pending/running guard — so a repo already syncing is skipped, and one repo
failing does not stop the rest.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from app.application.errors import ApplicationError, SyncAlreadyRunningError
from app.domain.entities.repository import Repository

logger = logging.getLogger(__name__)

_EPOCH = datetime.min.replace(tzinfo=UTC)


def least_recently_synced_first(repositories: list[Repository]) -> list[Repository]:
    """Order by ``last_synced_at`` ascending — never-synced first, then oldest.

    Fairness under rate pressure: a repo that failed keeps its stale timestamp and
    rises to the front of the next run, so no repository is permanently starved.
    """
    return sorted(repositories, key=lambda r: r.last_synced_at or _EPOCH)


class _Repositories(Protocol):
    async def list_all(self, *, enabled_only: bool = False) -> list[Repository]: ...


class _Trigger(Protocol):
    async def trigger_sync(
        self, repository_id: UUID, *, triggered_by: str, defer_seconds: float = 0.0
    ) -> object: ...


class _Organizations(Protocol):
    async def disabled_logins(self) -> set[str]: ...


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
        max_repos_per_run: int = 0,
        organizations: "_Organizations | None" = None,
    ) -> None:
        self._repositories = repositories
        self._use_cases = repository_use_cases
        self._stagger_seconds = stagger_seconds
        self._max_repos_per_run = max_repos_per_run
        self._organizations = organizations

    async def run(self) -> ScheduledSyncSummary:
        repositories = await self._repositories.list_all(enabled_only=True)
        disabled = (
            await self._organizations.disabled_logins() if self._organizations else set()
        )
        enqueued = skipped = failed = 0
        # Fairness: attempt least-recently-synced (incl. never-synced) first, then
        # cap the batch so a big org spreads across runs instead of starving the
        # tail when the rate budget runs out.
        eligible = []
        for r in least_recently_synced_first(repositories):
            if r.full_name.owner in disabled:
                skipped += 1  # organization sync is disabled by the admin
            else:
                eligible.append(r)
        deferred = 0
        if self._max_repos_per_run > 0 and len(eligible) > self._max_repos_per_run:
            deferred = len(eligible) - self._max_repos_per_run
            eligible = eligible[: self._max_repos_per_run]

        for repo in eligible:
            try:
                await self._use_cases.trigger_sync(
                    repo.id,
                    triggered_by="scheduler",
                    defer_seconds=enqueued * self._stagger_seconds,
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
            "scheduled full sync: enqueued=%d skipped=%d failed=%d deferred=%d "
            "over %d enabled repos",
            enqueued, skipped, failed, deferred, len(repositories),
        )
        return ScheduledSyncSummary(enqueued=enqueued, skipped=skipped, failed=failed)
