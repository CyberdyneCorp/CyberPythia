"""Integration test fixtures: real Postgres/Redis/MinIO from docker compose."""

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.infrastructure.persistence.models import Base

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://mnemosyne:mnemosyne@localhost:5433/mnemosyne"
)
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "localhost:9000")


def pytest_collection_modifyitems(config, items):
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)


@pytest.fixture
async def session_factory():
    """Session factory against the compose Postgres; tables truncated per test."""
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
        await conn.execute(text(f"TRUNCATE {tables} CASCADE"))
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()
