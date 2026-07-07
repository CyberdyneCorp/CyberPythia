"""DocumentPort and OpenSpecPort adapters."""

from uuid import UUID

from sqlalchemy import delete, select

from app.domain.entities.document import Document
from app.domain.entities.openspec_change import OpenSpecChange
from app.infrastructure.persistence.mappers import (
    document_to_entity,
    document_update_row,
    openspec_to_entity,
    openspec_update_row,
)
from app.infrastructure.persistence.models import DocumentRow, OpenSpecChangeRow
from app.infrastructure.persistence.repositories.base import PostgresRepositoryBase


class PostgresDocumentRepository(PostgresRepositoryBase):
    async def save(self, document: Document) -> None:
        async with self._session_factory() as session, session.begin():
            row = await session.scalar(
                select(DocumentRow).where(
                    DocumentRow.repository_id == document.repository_id,
                    DocumentRow.path == document.path,
                )
            )
            if row is None:
                row = DocumentRow(id=document.id)
                session.add(row)
            else:
                document.id = row.id
            document_update_row(row, document)

    async def get(self, document_id: UUID) -> Document | None:
        async with self._session_factory() as session:
            row = await session.get(DocumentRow, document_id)
            return document_to_entity(row) if row else None

    async def get_by_path(self, repository_id: UUID, path: str) -> Document | None:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(DocumentRow).where(
                    DocumentRow.repository_id == repository_id, DocumentRow.path == path
                )
            )
            return document_to_entity(row) if row else None

    async def list_by_repository(self, repository_id: UUID) -> list[Document]:
        async with self._session_factory() as session:
            rows = await session.scalars(
                select(DocumentRow)
                .where(DocumentRow.repository_id == repository_id)
                .order_by(DocumentRow.path)
            )
            return [document_to_entity(r) for r in rows]

    async def delete_missing(self, repository_id: UUID, seen_paths: set[str]) -> int:
        """Remove documents that disappeared from the repository since last sync."""
        async with self._session_factory() as session, session.begin():
            stmt = delete(DocumentRow).where(DocumentRow.repository_id == repository_id)
            if seen_paths:
                stmt = stmt.where(DocumentRow.path.not_in(seen_paths))
            result = await session.execute(stmt)
            return int(getattr(result, "rowcount", 0) or 0)


class PostgresOpenSpecRepository(PostgresRepositoryBase):
    async def save(self, change: OpenSpecChange) -> None:
        async with self._session_factory() as session, session.begin():
            row = await session.scalar(
                select(OpenSpecChangeRow).where(
                    OpenSpecChangeRow.repository_id == change.repository_id,
                    OpenSpecChangeRow.change_id == change.change_id,
                )
            )
            if row is None:
                row = OpenSpecChangeRow(id=change.id)
                session.add(row)
            else:
                change.id = row.id
            openspec_update_row(row, change)

    async def list_by_repository(self, repository_id: UUID) -> list[OpenSpecChange]:
        async with self._session_factory() as session:
            rows = await session.scalars(
                select(OpenSpecChangeRow)
                .where(OpenSpecChangeRow.repository_id == repository_id)
                .order_by(OpenSpecChangeRow.change_id)
            )
            return [openspec_to_entity(r) for r in rows]
