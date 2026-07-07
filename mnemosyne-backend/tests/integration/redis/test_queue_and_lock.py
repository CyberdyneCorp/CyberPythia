"""Integration tests for the Redis queue and sync lock (real Redis)."""

from uuid import uuid4

from arq import create_pool
from arq.connections import RedisSettings

from app.infrastructure.queue.redis_queue import ArqQueueAdapter, RedisSyncLock
from tests.integration.conftest import REDIS_URL


class TestRedisSyncLock:
    async def test_acquire_is_exclusive(self):
        lock = RedisSyncLock(REDIS_URL, ttl_seconds=10)
        repo_id = uuid4()
        try:
            assert await lock.acquire(repo_id)
            assert not await lock.acquire(repo_id)  # second acquire refused
            assert await lock.is_locked(repo_id)
        finally:
            await lock.release(repo_id)
            await lock.close()

    async def test_release_frees_lock(self):
        lock = RedisSyncLock(REDIS_URL, ttl_seconds=10)
        repo_id = uuid4()
        try:
            assert await lock.acquire(repo_id)
            await lock.release(repo_id)
            assert not await lock.is_locked(repo_id)
            assert await lock.acquire(repo_id)
        finally:
            await lock.release(repo_id)
            await lock.close()


class TestArqQueue:
    async def test_enqueue_lands_in_arq_queue(self):
        adapter = ArqQueueAdapter(REDIS_URL)
        job_payload = {"repository_id": str(uuid4())}
        try:
            await adapter.enqueue("sync_repository", payload=job_payload)
            pool = await create_pool(RedisSettings.from_dsn(REDIS_URL))
            queued = await pool.queued_jobs()
            names = [j.function for j in queued]
            assert "sync_repository" in names
            await pool.aclose()
        finally:
            await adapter.close()
