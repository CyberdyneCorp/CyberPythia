"""API key management endpoints — admin only (spec: rest-api, auth)."""

from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from app.application.audit import AuditService
from app.application.use_cases.api_keys import ApiKeyUseCases
from app.domain.entities.api_key import ApiKey
from app.interfaces.api.errors import NotFoundError
from app.interfaces.api.schemas.schemas import (
    ApiKeyCreatedResponse,
    ApiKeyCreateRequest,
    ApiKeyResponse,
)
from app.interfaces.api.security import AdminCaller, get_audit_service

router = APIRouter(prefix="/api/v1/api-keys", tags=["api-keys"])


def get_api_key_use_cases(request: Request) -> ApiKeyUseCases:
    return cast(ApiKeyUseCases, request.app.state.container.api_key_use_cases)


UseCases = Annotated[ApiKeyUseCases, Depends(get_api_key_use_cases)]
Audit = Annotated[AuditService, Depends(get_audit_service)]


def _metadata(key: ApiKey) -> dict[str, Any]:
    return {
        "id": key.id,
        "label": key.label,
        "prefix": key.prefix,
        "created_by": key.created_by,
        "created_at": key.created_at,
        "expires_at": key.expires_at,
        "revoked": key.revoked,
        "allowed_organizations": key.allowed_organizations,
    }


@router.post("", response_model=ApiKeyCreatedResponse, status_code=201)
async def create_api_key(
    body: ApiKeyCreateRequest, caller: AdminCaller, use_cases: UseCases, audit: Audit
) -> Any:
    created = await use_cases.create(
        label=body.label,
        created_by=caller.subject,
        expires_in_days=body.expires_in_days,
        allowed_organizations=body.allowed_organizations,
    )
    await audit.record(caller, "apikey.create", target=str(created.key.id))
    return ApiKeyCreatedResponse(key=created.plaintext, **_metadata(created.key))


@router.get("", response_model=list[ApiKeyResponse])
async def list_api_keys(caller: AdminCaller, use_cases: UseCases) -> Any:
    keys = await use_cases.list()
    return [ApiKeyResponse(**_metadata(k)) for k in keys]


@router.post("/{key_id}/revoke", status_code=204)
async def revoke_api_key(
    key_id: UUID, caller: AdminCaller, use_cases: UseCases, audit: Audit
) -> None:
    """Invalidate a key while keeping its record (audit trail)."""
    if not await use_cases.revoke(key_id):
        raise NotFoundError(f"api key '{key_id}' not found")
    await audit.record(caller, "apikey.revoke", target=str(key_id))


@router.delete("/{key_id}", status_code=204)
async def delete_api_key(
    key_id: UUID, caller: AdminCaller, use_cases: UseCases, audit: Audit
) -> None:
    """Permanently remove a key from the store."""
    if not await use_cases.delete(key_id):
        raise NotFoundError(f"api key '{key_id}' not found")
    await audit.record(caller, "apikey.delete", target=str(key_id))
