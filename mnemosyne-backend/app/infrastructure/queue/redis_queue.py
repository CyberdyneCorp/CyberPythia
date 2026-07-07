"""QueuePort and SyncLockPort adapters backed by Redis (arq for jobs)."""

from typing import Any
from uuid import UUID

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from redis.asyncio import Redis

from app.config import get_settings

LOCK_KEY_TEMPLATE = "sync:repo:{repository_id}:lock"


class ArqQueueAdapter:
    """Enqueues jobs onto the arq queue consumed by the worker service."""

    def __init__(self, redis_url: str | None = None) -> None:
        self._redis_url = redis_url or get_settings().redis_url
        self._pool: ArqRedis | None = None

    async def _get_pool(self) -> ArqRedis:
        if self._pool is None:
            self._pool = await create_pool(RedisSettings.from_dsn(self._redis_url))
        return self._pool

    async def enqueue(self, job_name: str, payload: dict[str, Any]) -> None:
        pool = await self._get_pool()
        await pool.enqueue_job(job_name, **payload)

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.aclose()
            self._pool = None


class RedisSyncLock:
    """Per-repository sync lock: SET NX with TTL (spec: repository-sync)."""

    def __init__(self, redis_url: str | None = None, ttl_seconds: int | None = None) -> None:
        settings = get_settings()
        self._redis: Redis = Redis.from_url(redis_url or settings.redis_url)
        self._ttl = ttl_seconds or settings.sync_lock_ttl_seconds

    def _key(self, repository_id: UUID) -> str:
        return LOCK_KEY_TEMPLATE.format(repository_id=repository_id)

    async def acquire(self, repository_id: UUID) -> bool:
        return bool(
            await self._redis.set(self._key(repository_id), "1", nx=True, ex=self._ttl)
        )

    async def release(self, repository_id: UUID) -> None:
        await self._redis.delete(self._key(repository_id))

    async def is_locked(self, repository_id: UUID) -> bool:
        return bool(await self._redis.exists(self._key(repository_id)))

    async def close(self) -> None:
        await self._redis.aclose()
