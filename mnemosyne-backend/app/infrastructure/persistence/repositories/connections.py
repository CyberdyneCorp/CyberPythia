"""ConnectionPort adapter."""

from uuid import UUID

from sqlalchemy import select

from app.domain.entities.github_connection import GitHubConnection
from app.infrastructure.persistence.mappers import connection_to_entity, connection_update_row
from app.infrastructure.persistence.models import GitHubConnectionRow
from app.infrastructure.persistence.repositories.base import PostgresRepositoryBase


class PostgresConnectionRepository(PostgresRepositoryBase):
    async def save(self, connection: GitHubConnection) -> None:
        async with self._session_factory() as session, session.begin():
            row = await session.get(GitHubConnectionRow, connection.id)
            if row is None:
                row = GitHubConnectionRow(id=connection.id)
                session.add(row)
            connection_update_row(row, connection)

    async def get(self, connection_id: UUID) -> GitHubConnection | None:
        async with self._session_factory() as session:
            row = await session.get(GitHubConnectionRow, connection_id)
            return connection_to_entity(row) if row else None

    async def get_by_owner(self, owner: str) -> GitHubConnection | None:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(GitHubConnectionRow).where(GitHubConnectionRow.owner == owner)
            )
            return connection_to_entity(row) if row else None

    async def list_all(self) -> list[GitHubConnection]:
        async with self._session_factory() as session:
            rows = await session.scalars(
                select(GitHubConnectionRow).order_by(GitHubConnectionRow.owner)
            )
            return [connection_to_entity(r) for r in rows]

    async def delete(self, connection_id: UUID) -> None:
        async with self._session_factory() as session, session.begin():
            row = await session.get(GitHubConnectionRow, connection_id)
            if row is not None:
                await session.delete(row)
