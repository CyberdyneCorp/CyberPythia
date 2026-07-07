"""FilePort, SyncJobPort, ContextPackPort, AuditPort, and metrics adapters."""

import hashlib
import json
from dataclasses import asdict
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select

from app.domain.entities.audit_record import AuditRecord
from app.domain.entities.context_pack import (
    ContextPack,
    DocRef,
    FileRef,
    IssueRef,
    OpenSpecRef,
    PullRequestRef,
    SourceChunkRef,
)
from app.domain.entities.source_chunk import SourceChunk
from app.domain.entities.source_file import SourceFile
from app.domain.entities.sync_job import SyncJob
from app.domain.value_objects.enums import IndexingMode
from app.infrastructure.persistence.mappers import (
    audit_to_entity,
    audit_to_row,
    source_chunk_to_entity,
    source_file_to_entity,
    sync_job_to_entity,
    sync_job_update_row,
)
from app.infrastructure.persistence.models import (
    AuditLogRow,
    ContextPackRow,
    RepositoryMetricsRow,
    SourceChunkRow,
    SourceFileRow,
    SyncJobRow,
)
from app.infrastructure.persistence.repositories.base import PostgresRepositoryBase


def _query_hash(query: str) -> str:
    return hashlib.sha256(query.strip().lower().encode()).hexdigest()


class PostgresFileRepository(PostgresRepositoryBase):
    async def replace_tree(self, repository_id: UUID, files: list[SourceFile]) -> None:
        """Reconcile the tree, preserving captured content + id for unchanged files.

        A file with the same path AND blob sha carries over its id and
        content-capture columns so the source-code step can skip it and its
        source_chunks (keyed by file id) stay valid across re-syncs.
        """
        async with self._session_factory() as session, session.begin():
            existing = {
                r.path: r
                for r in await session.scalars(
                    select(SourceFileRow).where(
                        SourceFileRow.repository_id == repository_id
                    )
                )
            }
            seen_paths = {f.path for f in files}
            for path, row in existing.items():
                if path not in seen_paths:
                    await session.delete(row)
            for f in files:
                prior = existing.get(f.path)
                if prior is not None and prior.sha == f.sha:
                    prior.language = f.language
                    prior.is_important = f.is_important
                    prior.important_kind = f.important_kind
                    prior.last_seen_at = f.last_seen_at
                    continue
                if prior is not None:
                    await session.delete(prior)  # sha changed -> fresh row (drops chunks)
                    await session.flush()
                session.add(
                    SourceFileRow(
                        id=f.id,
                        repository_id=f.repository_id,
                        path=f.path,
                        extension=f.extension,
                        language=f.language,
                        size_bytes=f.size_bytes,
                        sha=f.sha,
                        is_binary=f.is_binary,
                        is_important=f.is_important,
                        important_kind=f.important_kind,
                        last_seen_at=f.last_seen_at,
                    )
                )

    async def list_by_repository(self, repository_id: UUID) -> list[SourceFile]:
        async with self._session_factory() as session:
            rows = await session.scalars(
                select(SourceFileRow)
                .where(SourceFileRow.repository_id == repository_id)
                .order_by(SourceFileRow.path)
            )
            return [source_file_to_entity(r) for r in rows]

    async def get(self, file_id: UUID) -> SourceFile | None:
        async with self._session_factory() as session:
            row = await session.get(SourceFileRow, file_id)
            return source_file_to_entity(row) if row else None

    async def get_by_path(self, repository_id: UUID, path: str) -> SourceFile | None:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(SourceFileRow).where(
                    SourceFileRow.repository_id == repository_id, SourceFileRow.path == path
                )
            )
            return source_file_to_entity(row) if row else None

    async def save_content(self, file: SourceFile) -> None:
        async with self._session_factory() as session, session.begin():
            row = await session.get(SourceFileRow, file.id)
            if row is None:
                return
            row.content = file.content
            row.content_captured = file.content_captured
            row.content_hash = file.content_hash
            row.quarantined = file.quarantined


class PostgresSourceChunkRepository(PostgresRepositoryBase):
    async def replace_for_file(self, file_id: UUID, chunks: list[SourceChunk]) -> None:
        async with self._session_factory() as session, session.begin():
            await session.execute(
                delete(SourceChunkRow).where(SourceChunkRow.file_id == file_id)
            )
            for c in chunks:
                session.add(
                    SourceChunkRow(
                        id=c.id,
                        file_id=c.file_id,
                        repository_id=c.repository_id,
                        chunk_type=c.chunk_type.value,
                        symbol_name=c.symbol_name,
                        start_line=c.start_line,
                        end_line=c.end_line,
                        content=c.content,
                        content_hash=c.content_hash,
                    )
                )

    async def delete_for_file(self, file_id: UUID) -> None:
        async with self._session_factory() as session, session.begin():
            await session.execute(
                delete(SourceChunkRow).where(SourceChunkRow.file_id == file_id)
            )

    async def list_by_repository(self, repository_id: UUID) -> list[SourceChunk]:
        async with self._session_factory() as session:
            rows = await session.scalars(
                select(SourceChunkRow)
                .where(SourceChunkRow.repository_id == repository_id)
                .order_by(SourceChunkRow.start_line)
            )
            return [source_chunk_to_entity(r) for r in rows]

    async def get_by_symbol(
        self, repository_id: UUID, symbol_name: str
    ) -> list[SourceChunk]:
        async with self._session_factory() as session:
            rows = await session.scalars(
                select(SourceChunkRow).where(
                    SourceChunkRow.repository_id == repository_id,
                    SourceChunkRow.symbol_name == symbol_name,
                )
            )
            return [source_chunk_to_entity(r) for r in rows]


class PostgresSyncJobRepository(PostgresRepositoryBase):
    async def save(self, job: SyncJob) -> None:
        async with self._session_factory() as session, session.begin():
            row = await session.get(SyncJobRow, job.id)
            if row is None:
                row = SyncJobRow(id=job.id)
                session.add(row)
            sync_job_update_row(row, job)

    async def get(self, job_id: UUID) -> SyncJob | None:
        async with self._session_factory() as session:
            row = await session.get(SyncJobRow, job_id)
            return sync_job_to_entity(row) if row else None

    async def get_latest(self, repository_id: UUID) -> SyncJob | None:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(SyncJobRow)
                .where(SyncJobRow.repository_id == repository_id)
                .order_by(SyncJobRow.started_at.desc().nulls_last())
                .limit(1)
            )
            return sync_job_to_entity(row) if row else None


class PostgresContextPackRepository(PostgresRepositoryBase):
    async def save(self, pack: ContextPack) -> None:
        async with self._session_factory() as session, session.begin():
            payload = {
                "repository_summary": pack.repository_summary,
                "relevant_docs": [asdict(d) for d in pack.relevant_docs],
                "relevant_openspec_changes": [asdict(o) for o in pack.relevant_openspec_changes],
                "relevant_issues": [asdict(i) for i in pack.relevant_issues],
                "relevant_pull_requests": [asdict(p) for p in pack.relevant_pull_requests],
                "relevant_files": [asdict(f) for f in pack.relevant_files],
                "source_chunks": [asdict(c) for c in pack.source_chunks],
                "risks": pack.risks,
                "suggested_next_steps": pack.suggested_next_steps,
                "excluded_categories": pack.excluded_categories,
            }
            session.add(
                ContextPackRow(
                    id=pack.id,
                    repository_id=pack.repository_id,
                    query=pack.query,
                    query_hash=_query_hash(pack.query),
                    mode=pack.mode.value,
                    payload=json.loads(json.dumps(payload)),  # ensure JSON-serializable
                    sync_timestamp=pack.sync_timestamp.isoformat() if pack.sync_timestamp else "",
                    created_at=pack.created_at,
                )
            )

    async def find_cached(
        self, repository_id: UUID, query: str, mode: str, sync_timestamp: str
    ) -> ContextPack | None:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(ContextPackRow)
                .where(
                    ContextPackRow.repository_id == repository_id,
                    ContextPackRow.query_hash == _query_hash(query),
                    ContextPackRow.mode == mode,
                    ContextPackRow.sync_timestamp == sync_timestamp,
                )
                .order_by(ContextPackRow.created_at.desc().nulls_last())
                .limit(1)
            )
            if row is None:
                return None
            p = row.payload
            return ContextPack(
                id=row.id,
                repository_id=row.repository_id,
                query=row.query,
                mode=IndexingMode(row.mode),
                repository_summary=p.get("repository_summary", ""),
                relevant_docs=[DocRef(**d) for d in p.get("relevant_docs", [])],
                relevant_openspec_changes=[
                    OpenSpecRef(**o) for o in p.get("relevant_openspec_changes", [])
                ],
                relevant_issues=[IssueRef(**i) for i in p.get("relevant_issues", [])],
                relevant_pull_requests=[
                    PullRequestRef(**pr) for pr in p.get("relevant_pull_requests", [])
                ],
                relevant_files=[FileRef(**f) for f in p.get("relevant_files", [])],
                source_chunks=[SourceChunkRef(**c) for c in p.get("source_chunks", [])],
                risks=p.get("risks", []),
                suggested_next_steps=p.get("suggested_next_steps", []),
                excluded_categories=p.get("excluded_categories", []),
                sync_timestamp=datetime.fromisoformat(row.sync_timestamp)
                if row.sync_timestamp
                else None,
                created_at=row.created_at,
            )


class PostgresAuditRepository(PostgresRepositoryBase):
    async def record(self, entry: AuditRecord) -> None:
        async with self._session_factory() as session, session.begin():
            session.add(audit_to_row(entry))

    async def list_recent(self, limit: int = 100) -> list[AuditRecord]:
        async with self._session_factory() as session:
            rows = await session.scalars(
                select(AuditLogRow).order_by(AuditLogRow.occurred_at.desc()).limit(limit)
            )
            return [audit_to_entity(r) for r in rows]


class PostgresMetricsRepository(PostgresRepositoryBase):
    async def save(
        self,
        repository_id: UUID,
        *,
        issue_metrics: dict[str, Any],
        pr_metrics: dict[str, Any],
        summary: dict[str, Any],
        computed_at: datetime,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            row = await session.get(RepositoryMetricsRow, repository_id)
            if row is None:
                row = RepositoryMetricsRow(repository_id=repository_id)
                session.add(row)
            row.issue_metrics = issue_metrics
            row.pr_metrics = pr_metrics
            row.summary = summary
            row.computed_at = computed_at

    async def get(self, repository_id: UUID) -> dict[str, Any] | None:
        async with self._session_factory() as session:
            row = await session.get(RepositoryMetricsRow, repository_id)
            if row is None:
                return None
            return {
                "issue_metrics": row.issue_metrics,
                "pr_metrics": row.pr_metrics,
                "summary": row.summary,
                "computed_at": row.computed_at.isoformat(),
            }
