"""Process a validated webhook delivery: dispatch to incremental sync (spec: webhooks)."""

from datetime import UTC, datetime
from uuid import uuid4

from app.application.errors import ApplicationError, SyncAlreadyRunningError
from app.application.use_cases.incremental_sync import IncrementalSyncUseCases
from app.application.use_cases.repositories import RepositoryUseCases
from app.domain.entities.github_connection import GitHubConnection
from app.domain.entities.webhook_delivery import WebhookDelivery
from app.domain.entities.webhook_event import WebhookEvent
from app.domain.ports.persistence_ports import ConnectionPort, WebhookDeliveryPort
from app.domain.services import webhook_router
from app.domain.value_objects.enums import ConnectionKind, WebhookIntent


class ProcessWebhookDelivery:
    def __init__(
        self,
        deliveries: WebhookDeliveryPort,
        connections: ConnectionPort,
        incremental: IncrementalSyncUseCases,
        repository_use_cases: RepositoryUseCases,
    ) -> None:
        self._deliveries = deliveries
        self._connections = connections
        self._incremental = incremental
        self._repositories = repository_use_cases

    async def process(self, event: WebhookEvent) -> str:
        """Return the outcome ("processed" | "ignored" | "duplicate")."""
        if event.delivery_id and await self._deliveries.exists(event.delivery_id):
            return "duplicate"

        intent = webhook_router.route(event)
        outcome = await self._dispatch(intent, event)
        await self._record(event, outcome)
        return outcome

    async def _dispatch(self, intent: WebhookIntent, event: WebhookEvent) -> str:
        full_name = event.repository_full_name
        if intent is WebhookIntent.IGNORE or full_name is None:
            return "ignored"

        if intent is WebhookIntent.RECONCILE_INSTALLATION:
            return await self._reconcile(event.installation_id)

        if intent is WebhookIntent.SYNC_REPOSITORY:
            return await self._enqueue_sync(full_name)
        if intent is WebhookIntent.SYNC_ISSUE:
            done = await self._incremental.sync_issue(full_name, event.issue_number or 0)
            return "processed" if done else "ignored"
        if intent is WebhookIntent.SYNC_PULL_REQUEST:
            done = await self._incremental.sync_pull_request(
                full_name, event.pull_request_number or 0
            )
            return "processed" if done else "ignored"
        if intent is WebhookIntent.UPDATE_REPOSITORY:
            done = await self._incremental.update_repository_metadata(full_name)
            return "processed" if done else "ignored"
        if intent is WebhookIntent.REMOVE_REPOSITORY:
            done = await self._incremental.remove_repository(full_name)
            return "processed" if done else "ignored"
        return "ignored"

    async def _enqueue_sync(self, full_name: str) -> str:
        repo = await self._repositories.get_by_full_name(full_name)
        if repo is None or not repo.enabled:
            return "ignored"
        try:
            await self._repositories.trigger_sync(repo.id, triggered_by="webhook")
        except SyncAlreadyRunningError:
            return "processed"  # a sync is already covering these changes
        except ApplicationError:
            return "ignored"
        return "processed"

    async def _reconcile(self, installation_id: str | None) -> str:
        if installation_id is None:
            return "ignored"
        connection = await self._connection_for_installation(installation_id)
        if connection is None:
            return "ignored"
        await self._repositories.discover(connection.id)
        return "processed"

    async def _connection_for_installation(
        self, installation_id: str
    ) -> GitHubConnection | None:
        for c in await self._connections.list_all():
            if c.kind is ConnectionKind.GITHUB_APP and c.installation_id == installation_id:
                return c
        return None

    async def _record(self, event: WebhookEvent, outcome: str) -> None:
        if not event.delivery_id:
            return
        await self._deliveries.record(
            WebhookDelivery(
                id=uuid4(),
                delivery_id=event.delivery_id,
                event=event.event,
                action=event.action,
                repository_full_name=event.repository_full_name,
                outcome=outcome,
                received_at=datetime.now(UTC),
            )
        )
