"""arq worker: consumes sync jobs from Redis (design D4/D5).

Run with: `arq app.infrastructure.queue.worker.WorkerSettings`
"""

import logging
from datetime import UTC, datetime
from typing import Any, ClassVar
from uuid import UUID, uuid4

from arq.connections import RedisSettings
from arq.cron import cron

from app.composition import build_container
from app.config import get_settings
from app.domain.entities.sync_run import SyncRun

logger = logging.getLogger(__name__)

_settings = get_settings()


async def startup(ctx: dict[str, Any]) -> None:
    logging.basicConfig(level=logging.INFO)
    ctx["container"] = build_container()
    logger.info("mnemosyne-worker started")


async def shutdown(ctx: dict[str, Any]) -> None:
    container = ctx.get("container")
    if container is not None:
        await container.queue.close()
        await container.sync_lock.close()
        await container.github.close()


async def sync_repository(ctx: dict[str, Any], repository_id: str, job_id: str) -> str:
    container = ctx["container"]
    job = await container.sync_use_case.run(UUID(repository_id), UUID(job_id))
    logger.info("sync %s finished: %s", repository_id, job.status.value)
    return str(job.status.value)


async def delete_connection(ctx: dict[str, Any], connection_id: str) -> str:
    """Cascade-delete a connection and its indexed data off the request path."""
    container = ctx["container"]
    await container.connection_use_cases.perform_delete(UUID(connection_id))
    logger.info("connection %s deleted", connection_id)
    return connection_id


async def scheduled_full_sync(ctx: dict[str, Any]) -> str:
    """Daily cron: discover + auto-enable new repos, then enqueue a full sync of all enabled.

    Records a SyncRun history row so admins can watch runs via /api/v1/admin/sync-runs.
    """
    container = ctx["container"]
    started = datetime.now(UTC)
    discovered = newly_enabled = skipped_archived = 0
    if _settings.scheduled_discovery_enabled:
        d = await container.scheduled_discovery.run()
        discovered, newly_enabled, skipped_archived = (
            d.discovered, d.newly_enabled, d.skipped_archived
        )
    summary = await container.scheduled_sync.run()
    try:
        recorded = await container.readiness.record_snapshots()
        logger.info("recorded readiness snapshots for %d repositories", recorded)
    except Exception:
        logger.exception("readiness snapshot recording failed")
    try:
        await _deliver_digests(container)
    except Exception:
        logger.exception("digest delivery failed")
    try:
        await _prune_history(container)
    except Exception:
        logger.exception("history retention pruning failed")
    await container.sync_runs.record(
        SyncRun(
            id=uuid4(),
            trigger="scheduler",
            started_at=started,
            finished_at=datetime.now(UTC),
            discovered=discovered,
            newly_enabled=newly_enabled,
            skipped_archived=skipped_archived,
            enqueued=summary.enqueued,
            skipped=summary.skipped,
            failed=summary.failed,
        )
    )
    return (
        f"discovered={discovered} newly_enabled={newly_enabled} "
        f"enqueued={summary.enqueued} skipped={summary.skipped} failed={summary.failed}"
    )


async def _deliver_digests(container: Any) -> None:
    """POST each enabled org's non-empty attention digest to the alert webhook."""
    if not (_settings.alert_digest_enabled and container.notifier.configured):
        return
    orgs = await container.organizations.list_all()
    for org in orgs:
        if not org.sync_enabled:
            continue
        digest = await container.digest.build(org.login)
        if digest["is_empty"]:
            continue
        sent = await container.notifier.send(digest)
        logger.info("digest for %s delivered=%s", org.login, sent)


async def _prune_history(container: Any) -> None:
    """Delete metrics/readiness snapshots past the retention window (0 = keep all)."""
    days = _settings.history_retention_days
    if days <= 0:
        return
    metrics_removed = await container.metrics_history.prune(retention_days=days)
    readiness_removed = await container.readiness_history.prune(retention_days=days)
    logger.info(
        "history retention: pruned metrics=%d readiness=%d (older than %dd)",
        metrics_removed, readiness_removed, days,
    )


def _cron_jobs() -> list[Any]:
    if not _settings.scheduled_sync_enabled:
        return []
    return [
        cron(
            scheduled_full_sync,
            hour=_settings.scheduled_sync_hour,
            minute=_settings.scheduled_sync_minute,
            run_at_startup=False,
        )
    ]


class WorkerSettings:
    functions: ClassVar = [sync_repository, delete_connection]
    cron_jobs: ClassVar[list[Any]] = _cron_jobs()
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_jobs = 4
    job_timeout = 3600
