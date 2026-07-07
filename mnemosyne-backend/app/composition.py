"""Composition root: builds adapters and use cases for api/mcp/worker entrypoints."""

from dataclasses import dataclass
from functools import cached_property

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.audit import AuditService
from app.application.use_cases.context import ContextUseCases
from app.application.use_cases.github_connections import GitHubConnectionUseCases
from app.application.use_cases.repositories import RepositoryUseCases
from app.application.use_cases.sync_repository import MetricsWriter, SyncRepositoryUseCase
from app.config import Settings, get_settings
from app.infrastructure.auth.cyberdyne_auth import CyberdyneAuthAdapter
from app.infrastructure.github.client import GitHubClient
from app.infrastructure.llm.openai_answerer import OpenAIAnswerer
from app.infrastructure.object_storage.minio_storage import MinioStorageAdapter
from app.infrastructure.persistence.database import get_session_factory
from app.infrastructure.persistence.repositories.connections import PostgresConnectionRepository
from app.infrastructure.persistence.repositories.documents import (
    PostgresDocumentRepository,
    PostgresOpenSpecRepository,
)
from app.infrastructure.persistence.repositories.misc import (
    PostgresAuditRepository,
    PostgresContextPackRepository,
    PostgresFileRepository,
    PostgresMetricsRepository,
    PostgresSyncJobRepository,
)
from app.infrastructure.persistence.repositories.repositories import PostgresRepositoryRepository
from app.infrastructure.persistence.repositories.work_items import (
    PostgresIssueRepository,
    PostgresPullRequestRepository,
)
from app.infrastructure.queue.redis_queue import ArqQueueAdapter, RedisSyncLock
from app.infrastructure.security.token_encryption import TokenEncryption
from app.infrastructure.vector.pgvector_store import PgVectorEmbeddingStore


@dataclass
class Container:
    settings: Settings

    @cached_property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        return get_session_factory()

    # adapters ---------------------------------------------------------------

    @cached_property
    def auth_port(self) -> CyberdyneAuthAdapter:
        return CyberdyneAuthAdapter(settings=self.settings)

    @cached_property
    def github(self) -> GitHubClient:
        return GitHubClient(storage=self.storage, base_url=self.settings.github_api_base_url)

    @cached_property
    def storage(self) -> MinioStorageAdapter:
        return MinioStorageAdapter()

    @cached_property
    def queue(self) -> ArqQueueAdapter:
        return ArqQueueAdapter()

    @cached_property
    def sync_lock(self) -> RedisSyncLock:
        return RedisSyncLock()

    @cached_property
    def cipher(self) -> TokenEncryption:
        return TokenEncryption()

    @cached_property
    def embeddings(self) -> PgVectorEmbeddingStore:
        return PgVectorEmbeddingStore(self.session_factory)

    # persistence ------------------------------------------------------------

    @cached_property
    def connections(self) -> PostgresConnectionRepository:
        return PostgresConnectionRepository(self.session_factory)

    @cached_property
    def repositories(self) -> PostgresRepositoryRepository:
        return PostgresRepositoryRepository(self.session_factory)

    @cached_property
    def documents(self) -> PostgresDocumentRepository:
        return PostgresDocumentRepository(self.session_factory)

    @cached_property
    def openspec(self) -> PostgresOpenSpecRepository:
        return PostgresOpenSpecRepository(self.session_factory)

    @cached_property
    def issues(self) -> PostgresIssueRepository:
        return PostgresIssueRepository(self.session_factory)

    @cached_property
    def pull_requests(self) -> PostgresPullRequestRepository:
        return PostgresPullRequestRepository(self.session_factory)

    @cached_property
    def files(self) -> PostgresFileRepository:
        return PostgresFileRepository(self.session_factory)

    @cached_property
    def sync_jobs(self) -> PostgresSyncJobRepository:
        return PostgresSyncJobRepository(self.session_factory)

    @cached_property
    def context_packs(self) -> PostgresContextPackRepository:
        return PostgresContextPackRepository(self.session_factory)

    @cached_property
    def metrics_store(self) -> PostgresMetricsRepository:
        return PostgresMetricsRepository(self.session_factory)

    @cached_property
    def audit(self) -> PostgresAuditRepository:
        return PostgresAuditRepository(self.session_factory)

    # services / use cases ----------------------------------------------------

    @cached_property
    def audit_service(self) -> AuditService:
        return AuditService(self.audit)

    @cached_property
    def connection_use_cases(self) -> GitHubConnectionUseCases:
        return GitHubConnectionUseCases(self.connections, self.github, self.cipher)

    @cached_property
    def repository_use_cases(self) -> RepositoryUseCases:
        return RepositoryUseCases(
            self.repositories,
            self.connections,
            self.connection_use_cases,
            self.github,
            self.sync_jobs,
            self.queue,
            self.sync_lock,
        )

    @cached_property
    def context_use_cases(self) -> ContextUseCases:
        return ContextUseCases(
            repositories=self.repositories,
            documents=self.documents,
            openspec=self.openspec,
            issues=self.issues,
            pull_requests=self.pull_requests,
            files=self.files,
            context_packs=self.context_packs,
            embeddings=self.embeddings,
            answerer=OpenAIAnswerer(),
            metrics_store=self.metrics_store,
        )

    @cached_property
    def sync_use_case(self) -> SyncRepositoryUseCase:
        return SyncRepositoryUseCase(
            repositories=self.repositories,
            documents=self.documents,
            openspec=self.openspec,
            issues=self.issues,
            pull_requests=self.pull_requests,
            files=self.files,
            sync_jobs=self.sync_jobs,
            github=self.github,
            connection_use_cases=self.connection_use_cases,
            sync_lock=self.sync_lock,
            storage=self.storage,
            embeddings=self.embeddings,
            metrics_writer=MetricsWriter(store=self.metrics_store),
        )


def build_container() -> Container:
    return Container(settings=get_settings())
