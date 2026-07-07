"""RepositoryPort adapter."""

from uuid import UUID

from sqlalchemy import func, select

from app.domain.entities.repository import Repository
from app.infrastructure.persistence.mappers import repository_to_entity, repository_update_row
from app.infrastructure.persistence.models import RepositoryRow
from app.infrastructure.persistence.repositories.base import PostgresRepositoryBase


class PostgresRepositoryRepository(PostgresRepositoryBase):
    async def save(self, repository: Repository) -> None:
        await self.save_many([repository])

    async def save_many(self, repositories: list[Repository]) -> None:
        async with self._session_factory() as session, session.begin():
            for repository in repositories:
                row = await session.get(RepositoryRow, repository.id)
                if row is None:
                    # Discovery re-runs must not duplicate: match on github_id too.
                    row = await session.scalar(
                        select(RepositoryRow).where(RepositoryRow.github_id == repository.github_id)
                    )
                if row is None:
                    row = RepositoryRow(id=repository.id)
                    session.add(row)
                else:
                    repository.id = row.id
                repository_update_row(row, repository)

    async def get(self, repository_id: UUID) -> Repository | None:
        async with self._session_factory() as session:
            row = await session.get(RepositoryRow, repository_id)
            return repository_to_entity(row) if row else None

    async def get_by_full_name(self, full_name: str) -> Repository | None:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(RepositoryRow).where(RepositoryRow.full_name == full_name)
            )
            return repository_to_entity(row) if row else None

    async def list_all(self, *, enabled_only: bool = False) -> list[Repository]:
        async with self._session_factory() as session:
            stmt = select(RepositoryRow).order_by(func.lower(RepositoryRow.full_name))
            if enabled_only:
                stmt = stmt.where(RepositoryRow.enabled.is_(True))
            rows = await session.scalars(stmt)
            return [repository_to_entity(r) for r in rows]
