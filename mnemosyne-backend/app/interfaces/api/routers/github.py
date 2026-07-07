"""GitHub connection endpoints — admin only (spec: rest-api, github-connection)."""

from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from app.application.audit import AuditService
from app.application.errors import ApplicationError
from app.application.use_cases.github_connections import GitHubConnectionUseCases
from app.interfaces.api.mapping import translate_error
from app.interfaces.api.schemas.schemas import (
    AppConnectRequest,
    ConnectionResponse,
    ConnectionTestResponse,
    ConnectRequest,
    WebhookDeliveryResponse,
)
from app.interfaces.api.security import AdminCaller, get_audit_service

router = APIRouter(prefix="/api/v1/github", tags=["github"])
admin_router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def get_connection_use_cases(request: Request) -> GitHubConnectionUseCases:
    return cast(GitHubConnectionUseCases, request.app.state.container.connection_use_cases)


UseCases = Annotated[GitHubConnectionUseCases, Depends(get_connection_use_cases)]
Audit = Annotated[AuditService, Depends(get_audit_service)]


@router.post("/connect", response_model=ConnectionResponse, status_code=201)
async def connect(
    body: ConnectRequest, caller: AdminCaller, use_cases: UseCases, audit: Audit
) -> Any:
    try:
        view = await use_cases.connect(body.token)
    except ApplicationError as exc:
        raise translate_error(exc) from exc
    await audit.record(caller, "github.connect", target=view.owner)
    return view


@router.post("/app/connect", response_model=ConnectionResponse, status_code=201)
async def connect_app(
    body: AppConnectRequest, caller: AdminCaller, use_cases: UseCases, audit: Audit
) -> Any:
    try:
        view = await use_cases.connect_app(
            body.app_id, body.installation_id, body.private_key, body.webhook_secret
        )
    except ApplicationError as exc:
        raise translate_error(exc) from exc
    await audit.record(caller, "github.app_connect", target=view.owner)
    return view


@router.post("/app/installations/{connection_id}/repos", response_model=list[dict[str, Any]])
async def discover_app_repositories(
    connection_id: UUID, caller: AdminCaller, request: Request, audit: Audit
) -> Any:
    from app.interfaces.api.mapping import repository_response

    repo_use_cases = request.app.state.container.repository_use_cases
    try:
        repos = await repo_use_cases.discover(connection_id)
    except ApplicationError as exc:
        raise translate_error(exc) from exc
    await audit.record(caller, "github.app_discover", target=str(connection_id))
    return [repository_response(r).model_dump(mode="json") for r in repos]


@router.get("/connections", response_model=list[ConnectionResponse])
async def list_connections(caller: AdminCaller, use_cases: UseCases) -> Any:
    return await use_cases.list_connections()


@admin_router.get("/webhook-deliveries", response_model=list[WebhookDeliveryResponse])
async def webhook_deliveries(caller: AdminCaller, request: Request) -> Any:
    deliveries = await request.app.state.container.webhook_deliveries.list_recent(100)
    return [
        WebhookDeliveryResponse(
            delivery_id=d.delivery_id,
            event=d.event,
            action=d.action,
            repository_full_name=d.repository_full_name,
            outcome=d.outcome,
            received_at=d.received_at,
        )
        for d in deliveries
    ]


@router.post("/connections/{connection_id}/test", response_model=ConnectionTestResponse)
async def test_connection(
    connection_id: UUID, caller: AdminCaller, use_cases: UseCases, audit: Audit
) -> Any:
    try:
        result = await use_cases.test(connection_id)
    except ApplicationError as exc:
        raise translate_error(exc) from exc
    await audit.record(caller, "github.test", target=str(connection_id))
    return result


@router.delete("/connections/{connection_id}", status_code=204)
async def delete_connection(
    connection_id: UUID, caller: AdminCaller, use_cases: UseCases, audit: Audit
) -> None:
    try:
        await use_cases.delete(connection_id)
    except ApplicationError as exc:
        raise translate_error(exc) from exc
    await audit.record(caller, "github.disconnect", target=str(connection_id))
