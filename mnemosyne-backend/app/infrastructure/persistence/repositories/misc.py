"""FilePort, SyncJobPort, ContextPackPort, AuditPort, and metrics adapters."""

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.entities.agent_memory import AgentMemory
from app.domain.entities.api_key import ApiKey
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
from app.domain.entities.metrics_snapshot import MetricsSnapshot
from app.domain.entities.milestone import Milestone
from app.domain.entities.organization import Organization
from app.domain.entities.readiness_snapshot import ReadinessSnapshot
from app.domain.entities.source_chunk import SourceChunk
from app.domain.entities.source_file import SourceFile
from app.domain.entities.sync_job import SyncJob
from app.domain.entities.sync_run import SyncRun
from app.domain.entities.webhook_delivery import WebhookDelivery
from app.domain.services.org_scope import is_organization_allowed
from app.domain.value_objects.enums import IndexingMode
from app.infrastructure.persistence.mappers import (
    audit_to_entity,
    audit_to_row,
    source_chunk_to_entity,
    source_file_to_entity,
    sync_job_to_entity,
    sync_job_update_row,
    webhook_delivery_to_entity,
)
from app.infrastructure.persistence.models import (
    AgentMemoryRow,
    ApiKeyRow,
    AuditLogRow,
    ContextPackRow,
    MilestoneRow,
    OrganizationRow,
    RepositoryMetricsRow,
    RepositoryMetricsSnapshotRow,
    RepositoryReadinessSnapshotRow,
    SourceChunkRow,
    SourceFileRow,
    SyncJobRow,
    SyncRunHistoryRow,
    WebhookDeliveryRow,
)
from app.infrastructure.persistence.repositories.base import PostgresRepositoryBase

# Cap free-text memory search so a caller can't push an unbounded LIKE pattern.
_MAX_MEMORY_QUERY_LEN = 256


def _query_hash(query: str) -> str:
    return hashlib.sha256(query.strip().lower().encode()).hexdigest()


def _like_contains(query: str) -> str:
    """Escape LIKE metacharacters so a user query matches literally, never as a
    wildcard (CWE-89-like). Pair with ``ilike(..., escape="\\\\")``."""
    escaped = (
        query[:_MAX_MEMORY_QUERY_LEN]
        .replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )
    return f"%{escaped}%"


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

    async def list_recent(self, limit: int = 50) -> list[SyncJob]:
        async with self._session_factory() as session:
            rows = await session.scalars(
                select(SyncJobRow)
                .order_by(SyncJobRow.started_at.desc().nulls_last())
                .limit(limit)
            )
            return [sync_job_to_entity(r) for r in rows]


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
            return self._to_dict(row)

    async def list_all(self) -> dict[UUID, dict[str, Any]]:
        async with self._session_factory() as session:
            rows = (await session.execute(select(RepositoryMetricsRow))).scalars().all()
            return {row.repository_id: self._to_dict(row) for row in rows}

    @staticmethod
    def _to_dict(row: RepositoryMetricsRow) -> dict[str, Any]:
        return {
            "issue_metrics": row.issue_metrics,
            "pr_metrics": row.pr_metrics,
            "summary": row.summary,
            "computed_at": row.computed_at.isoformat(),
        }


class PostgresWebhookDeliveryRepository(PostgresRepositoryBase):
    async def exists(self, delivery_id: str) -> bool:
        async with self._session_factory() as session:
            found = await session.scalar(
                select(WebhookDeliveryRow.id).where(
                    WebhookDeliveryRow.delivery_id == delivery_id
                )
            )
            return found is not None

    async def record(self, delivery: WebhookDelivery) -> None:
        async with self._session_factory() as session, session.begin():
            session.add(
                WebhookDeliveryRow(
                    id=delivery.id,
                    delivery_id=delivery.delivery_id,
                    event=delivery.event,
                    action=delivery.action,
                    repository_full_name=delivery.repository_full_name,
                    outcome=delivery.outcome,
                    received_at=delivery.received_at,
                )
            )

    async def list_recent(self, limit: int = 100) -> list[WebhookDelivery]:
        async with self._session_factory() as session:
            rows = await session.scalars(
                select(WebhookDeliveryRow)
                .order_by(WebhookDeliveryRow.received_at.desc())
                .limit(limit)
            )
            return [webhook_delivery_to_entity(r) for r in rows]


class PostgresMetricsHistoryRepository(PostgresRepositoryBase):
    async def record(self, snapshot: MetricsSnapshot) -> None:
        async with self._session_factory() as session, session.begin():
            row = await session.scalar(
                select(RepositoryMetricsSnapshotRow).where(
                    RepositoryMetricsSnapshotRow.repository_id == snapshot.repository_id,
                    RepositoryMetricsSnapshotRow.captured_on == snapshot.captured_on,
                )
            )
            if row is None:
                row = RepositoryMetricsSnapshotRow(
                    id=uuid4(),
                    repository_id=snapshot.repository_id,
                    captured_on=snapshot.captured_on,
                )
                session.add(row)
            row.captured_at = snapshot.captured_at
            row.open_issues = snapshot.open_issues
            row.closed_issues = snapshot.closed_issues
            row.open_prs = snapshot.open_prs
            row.merged_prs = snapshot.merged_prs
            row.median_cycle_seconds = snapshot.median_cycle_seconds
            row.health_overall = snapshot.health_overall

    async def list_window(
        self, repository_id: UUID, *, days: int = 180
    ) -> list[MetricsSnapshot]:
        async with self._session_factory() as session:
            rows = await session.scalars(
                select(RepositoryMetricsSnapshotRow)
                .where(RepositoryMetricsSnapshotRow.repository_id == repository_id)
                .order_by(RepositoryMetricsSnapshotRow.captured_on.asc())
                .limit(days)
            )
            return [_snapshot_to_entity(r) for r in rows]

    async def list_all_windows(
        self, *, days: int = 180
    ) -> dict[UUID, list[MetricsSnapshot]]:
        async with self._session_factory() as session:
            rows = await session.scalars(
                select(RepositoryMetricsSnapshotRow).order_by(
                    RepositoryMetricsSnapshotRow.repository_id,
                    RepositoryMetricsSnapshotRow.captured_on.asc(),
                )
            )
            out: dict[UUID, list[MetricsSnapshot]] = {}
            for row in rows:
                out.setdefault(row.repository_id, []).append(_snapshot_to_entity(row))
            return out

    async def prune(self, *, retention_days: int) -> int:
        """Delete snapshots older than the retention window. 0 = keep all."""
        return await _prune_snapshots(
            self._session_factory, RepositoryMetricsSnapshotRow, retention_days
        )


def _snapshot_to_entity(row: RepositoryMetricsSnapshotRow) -> MetricsSnapshot:
    return MetricsSnapshot(
        repository_id=row.repository_id,
        captured_on=row.captured_on,
        captured_at=row.captured_at,
        open_issues=row.open_issues,
        closed_issues=row.closed_issues,
        open_prs=row.open_prs,
        merged_prs=row.merged_prs,
        median_cycle_seconds=row.median_cycle_seconds,
        health_overall=row.health_overall,
    )


class PostgresMemoryRepository(PostgresRepositoryBase):
    async def save(self, memory: AgentMemory) -> None:
        async with self._session_factory() as session, session.begin():
            row = await session.get(AgentMemoryRow, memory.id)
            if row is None:
                row = AgentMemoryRow(id=memory.id)
                session.add(row)
            row.repository_id = memory.repository_id
            row.organization = memory.organization
            row.kind = memory.kind
            row.content = memory.content
            row.author = memory.author
            row.created_at = memory.created_at

    async def get(self, memory_id: UUID) -> AgentMemory | None:
        async with self._session_factory() as session:
            row = await session.get(AgentMemoryRow, memory_id)
            return _memory_to_entity(row) if row else None

    async def _list(
        self, where: Any, kind: str | None, query: str | None, limit: int
    ) -> list[AgentMemory]:
        stmt = select(AgentMemoryRow).where(where)
        if kind:
            stmt = stmt.where(AgentMemoryRow.kind == kind)
        if query:
            stmt = stmt.where(
                AgentMemoryRow.content.ilike(_like_contains(query), escape="\\")
            )
        stmt = stmt.order_by(AgentMemoryRow.created_at.desc()).limit(limit)
        async with self._session_factory() as session:
            rows = await session.scalars(stmt)
            return [_memory_to_entity(r) for r in rows]

    async def list_for_repository(
        self, repository_id: UUID, *, kind: str | None = None,
        query: str | None = None, limit: int = 50,
    ) -> list[AgentMemory]:
        return await self._list(
            AgentMemoryRow.repository_id == repository_id, kind, query, limit
        )

    async def list_for_organization(
        self, organization: str, *, kind: str | None = None,
        query: str | None = None, limit: int = 50,
    ) -> list[AgentMemory]:
        # Defense-in-depth: out-of-scope orgs read as empty even if the use-case
        # gate is bypassed (mirrors the repository choke point).
        if not is_organization_allowed(organization):
            return []
        return await self._list(
            AgentMemoryRow.organization == organization, kind, query, limit
        )

    async def delete(self, memory_id: UUID) -> bool:
        async with self._session_factory() as session, session.begin():
            row = await session.get(AgentMemoryRow, memory_id)
            if row is None:
                return False
            await session.delete(row)
            return True


def _memory_to_entity(row: AgentMemoryRow) -> AgentMemory:
    return AgentMemory(
        id=row.id,
        content=row.content,
        kind=row.kind,
        author=row.author,
        created_at=row.created_at,
        repository_id=row.repository_id,
        organization=row.organization,
    )


async def _prune_snapshots(
    session_factory: async_sessionmaker[AsyncSession],
    row_type: type[Any],
    retention_days: int,
) -> int:
    """Delete snapshot rows with ``captured_on`` older than the retention window."""
    if retention_days <= 0:
        return 0
    cutoff = (datetime.now(UTC) - timedelta(days=retention_days)).date()
    async with session_factory() as session, session.begin():
        result = await session.execute(
            delete(row_type).where(row_type.captured_on < cutoff)
        )
        return int(getattr(result, "rowcount", 0) or 0)


class PostgresReadinessHistoryRepository(PostgresRepositoryBase):
    async def record(self, snapshot: ReadinessSnapshot) -> None:
        async with self._session_factory() as session, session.begin():
            row = await session.scalar(
                select(RepositoryReadinessSnapshotRow).where(
                    RepositoryReadinessSnapshotRow.repository_id == snapshot.repository_id,
                    RepositoryReadinessSnapshotRow.captured_on == snapshot.captured_on,
                )
            )
            if row is None:
                row = RepositoryReadinessSnapshotRow(
                    id=uuid4(),
                    repository_id=snapshot.repository_id,
                    captured_on=snapshot.captured_on,
                )
                session.add(row)
            row.captured_at = snapshot.captured_at
            row.gate = snapshot.gate

    async def list_for_repository(
        self, repository_id: UUID, *, limit: int = 180
    ) -> list[ReadinessSnapshot]:
        async with self._session_factory() as session:
            rows = await session.scalars(
                select(RepositoryReadinessSnapshotRow)
                .where(RepositoryReadinessSnapshotRow.repository_id == repository_id)
                .order_by(RepositoryReadinessSnapshotRow.captured_on.asc())
                .limit(limit)
            )
            return [_readiness_snapshot_to_entity(r) for r in rows]

    async def all_by_repository(self) -> dict[UUID, list[ReadinessSnapshot]]:
        async with self._session_factory() as session:
            rows = await session.scalars(
                select(RepositoryReadinessSnapshotRow).order_by(
                    RepositoryReadinessSnapshotRow.repository_id,
                    RepositoryReadinessSnapshotRow.captured_on.asc(),
                )
            )
            out: dict[UUID, list[ReadinessSnapshot]] = {}
            for row in rows:
                out.setdefault(row.repository_id, []).append(
                    _readiness_snapshot_to_entity(row)
                )
            return out

    async def prune(self, *, retention_days: int) -> int:
        """Delete snapshots older than the retention window. 0 = keep all."""
        return await _prune_snapshots(
            self._session_factory, RepositoryReadinessSnapshotRow, retention_days
        )


def _readiness_snapshot_to_entity(row: RepositoryReadinessSnapshotRow) -> ReadinessSnapshot:
    return ReadinessSnapshot(
        repository_id=row.repository_id,
        captured_on=row.captured_on,
        captured_at=row.captured_at,
        gate=row.gate,
    )


class PostgresMilestoneRepository(PostgresRepositoryBase):
    async def replace_for_repository(
        self, repository_id: UUID, milestones: list[Milestone]
    ) -> None:
        async with self._session_factory() as session, session.begin():
            prior = {
                r.number: r
                for r in await session.scalars(
                    select(MilestoneRow).where(
                        MilestoneRow.repository_id == repository_id
                    )
                )
            }
            seen: set[int] = set()
            for m in milestones:
                seen.add(m.number)
                row = prior.get(m.number) or MilestoneRow(
                    id=uuid4(), repository_id=repository_id
                )
                if m.number not in prior:
                    session.add(row)
                row.number = m.number
                row.title = m.title
                row.state = m.state
                row.due_on = m.due_on
                row.open_issues = m.open_issues
                row.closed_issues = m.closed_issues
                row.updated_at = m.updated_at
            for number, row in prior.items():
                if number not in seen:
                    await session.delete(row)

    async def list_by_repository(self, repository_id: UUID) -> list[Milestone]:
        async with self._session_factory() as session:
            rows = await session.scalars(
                select(MilestoneRow)
                .where(MilestoneRow.repository_id == repository_id)
                .order_by(MilestoneRow.number.asc())
            )
            return [_milestone_to_entity(r) for r in rows]

    async def list_all(self) -> dict[UUID, list[Milestone]]:
        async with self._session_factory() as session:
            rows = await session.scalars(
                select(MilestoneRow).order_by(
                    MilestoneRow.repository_id, MilestoneRow.number.asc()
                )
            )
            out: dict[UUID, list[Milestone]] = {}
            for row in rows:
                out.setdefault(row.repository_id, []).append(_milestone_to_entity(row))
            return out


def _milestone_to_entity(row: MilestoneRow) -> Milestone:
    return Milestone(
        id=row.id,
        repository_id=row.repository_id,
        number=row.number,
        title=row.title,
        state=row.state,
        due_on=row.due_on,
        open_issues=row.open_issues,
        closed_issues=row.closed_issues,
        updated_at=row.updated_at,
    )


class PostgresSyncRunRepository(PostgresRepositoryBase):
    async def record(self, run: SyncRun) -> None:
        async with self._session_factory() as session, session.begin():
            session.add(
                SyncRunHistoryRow(
                    id=run.id,
                    trigger=run.trigger,
                    started_at=run.started_at,
                    finished_at=run.finished_at,
                    discovered=run.discovered,
                    newly_enabled=run.newly_enabled,
                    skipped_archived=run.skipped_archived,
                    enqueued=run.enqueued,
                    skipped=run.skipped,
                    failed=run.failed,
                )
            )

    async def list_recent(self, limit: int = 50) -> list[SyncRun]:
        async with self._session_factory() as session:
            rows = await session.scalars(
                select(SyncRunHistoryRow)
                .order_by(SyncRunHistoryRow.finished_at.desc())
                .limit(limit)
            )
            return [_sync_run_to_entity(r) for r in rows]


def _sync_run_to_entity(row: SyncRunHistoryRow) -> SyncRun:
    return SyncRun(
        id=row.id,
        trigger=row.trigger,
        started_at=row.started_at,
        finished_at=row.finished_at,
        discovered=row.discovered,
        newly_enabled=row.newly_enabled,
        skipped_archived=row.skipped_archived,
        enqueued=row.enqueued,
        skipped=row.skipped,
        failed=row.failed,
    )


class PostgresOrganizationRepository(PostgresRepositoryBase):
    async def upsert_many(self, logins: list[str], *, default_enabled: bool) -> None:
        async with self._session_factory() as session, session.begin():
            existing = {
                r.login
                for r in await session.scalars(
                    select(OrganizationRow).where(OrganizationRow.login.in_(logins))
                )
            }
            for login in set(logins):
                if login not in existing:
                    session.add(
                        OrganizationRow(
                            id=uuid4(), login=login, sync_enabled=default_enabled
                        )
                    )

    async def list_all(self) -> list[Organization]:
        async with self._session_factory() as session:
            rows = await session.scalars(
                select(OrganizationRow).order_by(func.lower(OrganizationRow.login))
            )
            return [Organization(login=r.login, sync_enabled=r.sync_enabled) for r in rows]

    async def set_enabled(self, login: str, *, enabled: bool) -> Organization | None:
        async with self._session_factory() as session, session.begin():
            row = await session.scalar(
                select(OrganizationRow).where(OrganizationRow.login == login)
            )
            if row is None:
                return None
            row.sync_enabled = enabled
            return Organization(login=row.login, sync_enabled=enabled)

    async def disabled_logins(self) -> set[str]:
        async with self._session_factory() as session:
            rows = await session.scalars(
                select(OrganizationRow.login).where(OrganizationRow.sync_enabled.is_(False))
            )
            return set(rows)


def _api_key_to_entity(row: ApiKeyRow) -> ApiKey:
    return ApiKey(
        id=row.id,
        label=row.label,
        prefix=row.prefix,
        key_hash=row.key_hash,
        created_by=row.created_by,
        created_at=row.created_at,
        expires_at=row.expires_at,
        revoked=row.revoked,
        allowed_organizations=row.allowed_organizations,
    )


class PostgresApiKeyRepository(PostgresRepositoryBase):
    async def save(self, key: ApiKey) -> None:
        async with self._session_factory() as session, session.begin():
            session.add(
                ApiKeyRow(
                    id=key.id,
                    label=key.label,
                    prefix=key.prefix,
                    key_hash=key.key_hash,
                    created_by=key.created_by,
                    created_at=key.created_at,
                    expires_at=key.expires_at,
                    revoked=key.revoked,
                    allowed_organizations=key.allowed_organizations,
                )
            )

    async def get_by_hash(self, key_hash: str) -> ApiKey | None:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(ApiKeyRow).where(ApiKeyRow.key_hash == key_hash)
            )
            return _api_key_to_entity(row) if row else None

    async def list_all(self) -> list[ApiKey]:
        async with self._session_factory() as session:
            rows = await session.scalars(
                select(ApiKeyRow).order_by(ApiKeyRow.created_at.desc())
            )
            return [_api_key_to_entity(r) for r in rows]

    async def revoke(self, key_id: UUID) -> bool:
        async with self._session_factory() as session, session.begin():
            row = await session.scalar(select(ApiKeyRow).where(ApiKeyRow.id == key_id))
            if row is None:
                return False
            row.revoked = True
            return True

    async def delete(self, key_id: UUID) -> bool:
        async with self._session_factory() as session, session.begin():
            row = await session.scalar(select(ApiKeyRow).where(ApiKeyRow.id == key_id))
            if row is None:
                return False
            await session.delete(row)
            return True
