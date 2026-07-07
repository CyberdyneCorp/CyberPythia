"""Shared base for Postgres repository adapters."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class PostgresRepositoryBase:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
