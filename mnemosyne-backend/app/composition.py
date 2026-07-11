"""Composition root: builds adapters and use cases for api/mcp/worker entrypoints."""

from dataclasses import dataclass
from functools import cached_property

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.audit import AuditService
from app.application.metrics_recompute import MetricsRecomputeService
from app.application.use_cases.api_keys import ApiKeyUseCases
from app.application.use_cases.capabilities import CapabilitiesService
from app.application.use_cases.code import CodeUseCases
from app.application.use_cases.context import ContextUseCases
from app.application.use_cases.cross_repo import CrossRepoService
from app.application.use_cases.delivery_intelligence import DeliveryIntelligenceService
from app.application.use_cases.digest import DigestService
from app.application.use_cases.github_connections import GitHubConnectionUseCases
from app.application.use_cases.incremental_sync import IncrementalSyncUseCases
from app.application.use_cases.intelligence import IntelligenceService
from app.application.use_cases.memory import MemoryService
from app.application.use_cases.process_webhook import ProcessWebhookDelivery
from app.application.use_cases.readiness import ReadinessService
from app.application.use_cases.repositories import RepositoryUseCases
from app.application.use_cases.scheduled_discovery import ScheduledDiscoveryService
from app.application.use_cases.scheduled_sync import ScheduledSyncService
from app.application.use_cases.security import SecurityService
from app.application.use_cases.sync_repository import MetricsWriter, SyncRepositoryUseCase
from app.config import Settings, get_settings
from app.domain.services.code_chunker import HeuristicCodeChunker
from app.domain.services.repository_health import RepositoryHealthService
from app.domain.services.repository_signals import RepositorySignalsService
from app.domain.value_objects.enums import IndexingMode
from app.infrastructure.auth.api_key_auth import ApiKeyAuthAdapter
from app.infrastructure.auth.cyberdyne_auth import CyberdyneAuthAdapter
from app.infrastructure.github.app_auth import GitHubAppAuth
from app.infrastructure.github.client import GitHubClient
from app.infrastructure.llm.openai_answerer import OpenAIAnswerer
from app.infrastructure.notify.webhook_notifier import WebhookNotifier
from app.infrastructure.object_storage.minio_storage import MinioStorageAdapter
from app.infrastructure.persistence.database import get_session_factory
from app.infrastructure.persistence.repositories.connections import PostgresConnectionRepository
from app.infrastructure.persistence.repositories.documents import (
    PostgresDocumentRepository,
    PostgresOpenSpecRepository,
)
from app.infrastructure.persistence.repositories.misc import (
    PostgresApiKeyRepository,
    PostgresAuditRepository,
    PostgresContextPackRepository,
    PostgresFileRepository,
    PostgresMemoryRepository,
    PostgresMetricsHistoryRepository,
    PostgresMetricsRepository,
    PostgresMilestoneRepository,
    PostgresOrganizationRepository,
    PostgresReadinessHistoryRepository,
    PostgresSourceChunkRepository,
    PostgresSyncJobRepository,
    PostgresSyncRunRepository,
    PostgresWebhookDeliveryRepository,
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
    def cyberdyne_auth(self) -> CyberdyneAuthAdapter:
        return CyberdyneAuthAdapter(settings=self.settings)

    @cached_property
    def auth_port(self) -> ApiKeyAuthAdapter:
        # Mnemosyne API keys first, CyberdyneAuth tokens otherwise.
        return ApiKeyAuthAdapter(
            api_keys=self.api_keys,
            fallback=self.cyberdyne_auth,
            entitlement=self.settings.required_entitlement,
        )

    @cached_property
    def github(self) -> GitHubClient:
        return GitHubClient(
            storage=self.storage,
            base_url=self.settings.github_api_base_url,
            max_wait_seconds=self.settings.github_rate_limit_max_wait_seconds,
        )

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
    def source_chunks(self) -> PostgresSourceChunkRepository:
        return PostgresSourceChunkRepository(self.session_factory)

    @cached_property
    def code_chunker(self) -> HeuristicCodeChunker:
        return HeuristicCodeChunker(
            window_lines=self.settings.code_window_lines,
            overlap=self.settings.code_window_overlap,
        )

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
    def metrics_history(self) -> PostgresMetricsHistoryRepository:
        return PostgresMetricsHistoryRepository(self.session_factory)

    @cached_property
    def readiness_history(self) -> PostgresReadinessHistoryRepository:
        return PostgresReadinessHistoryRepository(self.session_factory)

    @cached_property
    def memories(self) -> PostgresMemoryRepository:
        return PostgresMemoryRepository(self.session_factory)

    @cached_property
    def memory(self) -> MemoryService:
        return MemoryService(self.memories, self.repositories)

    @cached_property
    def notifier(self) -> WebhookNotifier:
        return WebhookNotifier(self.settings.alert_webhook_url or None)

    @cached_property
    def digest(self) -> DigestService:
        return DigestService(self.readiness, self.cross_repo, self.delivery_intelligence)

    @cached_property
    def security(self) -> SecurityService:
        return SecurityService(self.repositories, self.metrics_store)

    @cached_property
    def milestones(self) -> PostgresMilestoneRepository:
        return PostgresMilestoneRepository(self.session_factory)

    @cached_property
    def audit(self) -> PostgresAuditRepository:
        return PostgresAuditRepository(self.session_factory)

    @cached_property
    def api_keys(self) -> PostgresApiKeyRepository:
        return PostgresApiKeyRepository(self.session_factory)

    # services / use cases ----------------------------------------------------

    @cached_property
    def audit_service(self) -> AuditService:
        return AuditService(self.audit)

    @cached_property
    def api_key_use_cases(self) -> ApiKeyUseCases:
        return ApiKeyUseCases(self.api_keys)

    @cached_property
    def cross_repo(self) -> CrossRepoService:
        return CrossRepoService(
            self.repositories, self.issues, self.pull_requests, self.embeddings
        )

    @cached_property
    def capabilities(self) -> CapabilitiesService:
        return CapabilitiesService(
            self.repositories, self.documents, self.openspec, self.metrics_store
        )

    @cached_property
    def readiness(self) -> ReadinessService:
        return ReadinessService(
            self.repositories, self.files, self.documents, self.openspec,
            self.metrics_store, RepositorySignalsService(),
            history=self.readiness_history,
        )

    @cached_property
    def app_auth(self) -> GitHubAppAuth:
        return GitHubAppAuth()

    @cached_property
    def connection_use_cases(self) -> GitHubConnectionUseCases:
        return GitHubConnectionUseCases(
            self.connections, self.github, self.cipher, app_auth=self.app_auth,
            repositories=self.repositories, queue=self.queue,
            public_api_base_url=self.settings.public_api_base_url,
            github_web_base_url=self.settings.github_web_base_url,
            state_secret=self.settings.token_encryption_key,
        )

    @cached_property
    def metrics_recompute(self) -> MetricsRecomputeService:
        return MetricsRecomputeService(
            self.issues,
            self.pull_requests,
            self.documents,
            self.openspec,
            self.metrics_store,
            history=self.metrics_history,
        )

    @cached_property
    def incremental_sync(self) -> IncrementalSyncUseCases:
        return IncrementalSyncUseCases(
            self.repositories,
            self.issues,
            self.pull_requests,
            self.github,
            self.connection_use_cases,
            self.metrics_recompute,
        )

    @cached_property
    def process_webhook(self) -> ProcessWebhookDelivery:
        return ProcessWebhookDelivery(
            self.webhook_deliveries,
            self.connections,
            self.incremental_sync,
            self.repository_use_cases,
        )

    @cached_property
    def webhook_deliveries(self) -> PostgresWebhookDeliveryRepository:
        return PostgresWebhookDeliveryRepository(self.session_factory)

    @cached_property
    def sync_runs(self) -> PostgresSyncRunRepository:
        return PostgresSyncRunRepository(self.session_factory)

    @cached_property
    def organizations(self) -> PostgresOrganizationRepository:
        return PostgresOrganizationRepository(self.session_factory)

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
            organizations=self.organizations,
            default_org_sync_enabled=self.settings.default_org_sync_enabled,
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
            source_chunks=self.source_chunks,
            code_chunker=self.code_chunker,
            milestones=self.milestones,
            metrics_history=self.metrics_history,
            source_size_cap=self.settings.source_size_cap_bytes,
        )

    @cached_property
    def code_use_cases(self) -> CodeUseCases:
        return CodeUseCases(
            repositories=self.repositories,
            files=self.files,
            source_chunks=self.source_chunks,
            embeddings=self.embeddings,
            audit=self.audit_service,
        )

    @cached_property
    def intelligence(self) -> IntelligenceService:
        return IntelligenceService(
            repositories=self.repositories,
            files=self.files,
            metrics=self.metrics_store,
            signals=RepositorySignalsService(),
            health=RepositoryHealthService(),
        )

    @cached_property
    def scheduled_sync(self) -> ScheduledSyncService:
        return ScheduledSyncService(
            self.repositories,
            self.repository_use_cases,
            stagger_seconds=self.settings.scheduled_sync_stagger_seconds,
            organizations=self.organizations,
        )

    @cached_property
    def scheduled_discovery(self) -> ScheduledDiscoveryService:
        return ScheduledDiscoveryService(
            self.repositories,
            self.connections,
            self.repository_use_cases,
            auto_enable=self.settings.auto_enable_new_repos,
            mode=IndexingMode(self.settings.auto_enable_mode),
            include_archived=self.settings.auto_enable_archived,
            organizations=self.organizations,
        )

    @cached_property
    def delivery_intelligence(self) -> DeliveryIntelligenceService:
        return DeliveryIntelligenceService(
            repositories=self.repositories,
            issues=self.issues,
            pull_requests=self.pull_requests,
            milestones=self.milestones,
            history=self.metrics_history,
            metrics=self.metrics_store,
        )


def build_container() -> Container:
    return Container(settings=get_settings())
