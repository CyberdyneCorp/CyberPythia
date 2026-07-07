"""arq worker: consumes sync jobs from Redis (design D4/D5).

Run with: `arq app.infrastructure.queue.worker.WorkerSettings`
"""

import logging
from typing import Any, ClassVar
from uuid import UUID

from arq.connections import RedisSettings

from app.composition import build_container
from app.config import get_settings

logger = logging.getLogger(__name__)


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


class WorkerSettings:
    functions: ClassVar = [sync_repository]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_jobs = 4
    job_timeout = 3600
