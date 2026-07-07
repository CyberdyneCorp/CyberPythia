"""SQLAlchemy ORM models. Domain entities are mapped in the repository adapters."""

import uuid
from datetime import date, datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON

# JSONB on Postgres, plain JSON elsewhere (unit tests on SQLite)
JsonType = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


class TimestampedMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class GitHubConnectionRow(Base, TimestampedMixin):
    __tablename__ = "github_connections"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    owner: Mapped[str] = mapped_column(String(200), unique=True)
    owner_type: Mapped[str] = mapped_column(String(20))
    kind: Mapped[str] = mapped_column(String(20), default="pat")
    encrypted_token: Mapped[bytes | None] = mapped_column(LargeBinary)
    token_hint: Mapped[str] = mapped_column(String(8), default="")
    app_id: Mapped[str | None] = mapped_column(String(50))
    installation_id: Mapped[str | None] = mapped_column(String(50), index=True)
    encrypted_private_key: Mapped[bytes | None] = mapped_column(LargeBinary)
    encrypted_webhook_secret: Mapped[bytes | None] = mapped_column(LargeBinary)
    permissions: Mapped[list[str]] = mapped_column(JsonType, default=list)
    status: Mapped[str] = mapped_column(String(20), default="active")


class WebhookDeliveryRow(Base):
    __tablename__ = "webhook_deliveries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    delivery_id: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    event: Mapped[str] = mapped_column(String(60))
    action: Mapped[str | None] = mapped_column(String(60))
    repository_full_name: Mapped[str | None] = mapped_column(String(300))
    outcome: Mapped[str] = mapped_column(String(20))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class RepositoryRow(Base):
    __tablename__ = "repositories"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("github_connections.id", ondelete="CASCADE")
    )
    github_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    full_name: Mapped[str] = mapped_column(String(300), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    visibility: Mapped[str] = mapped_column(String(20))
    default_branch: Mapped[str] = mapped_column(String(200))
    primary_language: Mapped[str | None] = mapped_column(String(100))
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    github_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    indexing_mode: Mapped[str] = mapped_column(String(30), default="docs_only")
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DocumentRow(Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("repository_id", "path"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), index=True
    )
    path: Mapped[str] = mapped_column(String(1000))
    type: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(500))
    content: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    last_commit_sha: Mapped[str | None] = mapped_column(String(64))
    quarantined: Mapped[bool] = mapped_column(Boolean, default=False)
    embedding_status: Mapped[str] = mapped_column(String(20), default="pending")
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DocumentChunkRow(Base):
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[Any] = mapped_column(Vector(1536), nullable=True)


class OpenSpecChangeRow(Base):
    __tablename__ = "openspec_changes"
    __table_args__ = (UniqueConstraint("repository_id", "change_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), index=True
    )
    change_id: Mapped[str] = mapped_column(String(300))
    path: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(20), default="unknown")
    proposal: Mapped[str | None] = mapped_column(Text)
    design: Mapped[str | None] = mapped_column(Text)
    tasks: Mapped[str | None] = mapped_column(Text)
    affected_specs: Mapped[list[str]] = mapped_column(JsonType, default=list)
    content_hash: Mapped[str] = mapped_column(String(64), default="")


class IssueRow(Base):
    __tablename__ = "issues"
    __table_args__ = (
        UniqueConstraint("repository_id", "number"),
        Index("ix_issues_repo_state", "repository_id", "state"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), index=True
    )
    github_issue_id: Mapped[int] = mapped_column(BigInteger)
    number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(20))
    author: Mapped[str | None] = mapped_column(String(200))
    labels: Mapped[list[str]] = mapped_column(JsonType, default=list)
    assignees: Mapped[list[str]] = mapped_column(JsonType, default=list)
    milestone: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    comments_count: Mapped[int] = mapped_column(Integer, default=0)
    first_response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reopened_count: Mapped[int] = mapped_column(Integer, default=0)


class PullRequestRow(Base):
    __tablename__ = "pull_requests"
    __table_args__ = (
        UniqueConstraint("repository_id", "number"),
        Index("ix_prs_repo_state", "repository_id", "state"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), index=True
    )
    github_pr_id: Mapped[int] = mapped_column(BigInteger)
    number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(20))
    merged: Mapped[bool] = mapped_column(Boolean, default=False)
    author: Mapped[str | None] = mapped_column(String(200))
    reviewers: Mapped[list[str]] = mapped_column(JsonType, default=list)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    merged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    changed_files: Mapped[int] = mapped_column(Integer, default=0)
    additions: Mapped[int] = mapped_column(Integer, default=0)
    deletions: Mapped[int] = mapped_column(Integer, default=0)
    review_decision: Mapped[str | None] = mapped_column(String(50))


class SourceFileRow(Base):
    __tablename__ = "source_files"
    __table_args__ = (UniqueConstraint("repository_id", "path"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), index=True
    )
    path: Mapped[str] = mapped_column(String(1000))
    extension: Mapped[str | None] = mapped_column(String(50))
    language: Mapped[str | None] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    sha: Mapped[str] = mapped_column(String(64))
    is_binary: Mapped[bool] = mapped_column(Boolean, default=False)
    is_important: Mapped[bool] = mapped_column(Boolean, default=False)
    important_kind: Mapped[str | None] = mapped_column(String(50))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Source-content capture (mode: code_context / full_context)
    content: Mapped[str | None] = mapped_column(Text)
    content_captured: Mapped[bool] = mapped_column(Boolean, default=False)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    quarantined: Mapped[bool] = mapped_column(Boolean, default=False)


class SourceChunkRow(Base):
    __tablename__ = "source_chunks"
    __table_args__ = (
        Index("ix_source_chunks_repo", "repository_id"),
        Index("ix_source_chunks_symbol", "repository_id", "symbol_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    file_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_files.id", ondelete="CASCADE"), index=True
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE")
    )
    chunk_type: Mapped[str] = mapped_column(String(20))
    symbol_name: Mapped[str | None] = mapped_column(String(300))
    start_line: Mapped[int] = mapped_column(Integer)
    end_line: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    embedding: Mapped[Any] = mapped_column(Vector(1536), nullable=True)


class SyncJobRow(Base):
    __tablename__ = "sync_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), index=True
    )
    mode: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, default=list)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    triggered_by: Mapped[str | None] = mapped_column(String(200))


class RepositoryMetricsRow(Base):
    __tablename__ = "repository_metrics"

    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), primary_key=True
    )
    issue_metrics: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    pr_metrics: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    summary: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RepositoryMetricsSnapshotRow(Base):
    __tablename__ = "repository_metrics_snapshots"
    __table_args__ = (UniqueConstraint("repository_id", "captured_on"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), index=True
    )
    captured_on: Mapped[date] = mapped_column(Date)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    open_issues: Mapped[int] = mapped_column(Integer, default=0)
    closed_issues: Mapped[int] = mapped_column(Integer, default=0)
    open_prs: Mapped[int] = mapped_column(Integer, default=0)
    merged_prs: Mapped[int] = mapped_column(Integer, default=0)
    median_cycle_seconds: Mapped[float | None] = mapped_column(Float)
    health_overall: Mapped[float | None] = mapped_column(Float)


class MilestoneRow(Base):
    __tablename__ = "milestones"
    __table_args__ = (UniqueConstraint("repository_id", "number"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), index=True
    )
    number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(20))
    due_on: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    open_issues: Mapped[int] = mapped_column(Integer, default=0)
    closed_issues: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ContextPackRow(Base):
    __tablename__ = "context_packs"
    __table_args__ = (
        Index("ix_context_packs_cache", "repository_id", "query_hash", "mode", "sync_timestamp"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), index=True
    )
    query: Mapped[str] = mapped_column(Text)
    query_hash: Mapped[str] = mapped_column(String(64))
    mode: Mapped[str] = mapped_column(String(30))
    payload: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    sync_timestamp: Mapped[str] = mapped_column(String(40), default="")
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLogRow(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    subject: Mapped[str] = mapped_column(String(200), index=True)
    client_id: Mapped[str | None] = mapped_column(String(200))
    operation: Mapped[str] = mapped_column(String(200))
    target: Mapped[str | None] = mapped_column(String(500))
    outcome: Mapped[str] = mapped_column(String(20))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
