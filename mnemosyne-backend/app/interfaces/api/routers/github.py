"""GitHub connection endpoints — admin only (spec: rest-api, github-connection)."""

from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from app.application.audit import AuditService
from app.application.errors import ApplicationError
from app.application.use_cases.github_connections import GitHubConnectionUseCases
from app.interfaces.api.mapping import translate_error
from app.interfaces.api.schemas.schemas import (
    ConnectionResponse,
    ConnectionTestResponse,
    ConnectRequest,
)
from app.interfaces.api.security import AdminCaller, get_audit_service

router = APIRouter(prefix="/api/v1/github", tags=["github"])


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


@router.get("/connections", response_model=list[ConnectionResponse])
async def list_connections(caller: AdminCaller, use_cases: UseCases) -> Any:
    return await use_cases.list_connections()


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
