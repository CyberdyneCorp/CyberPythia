"""Bearer authentication + authorization dependencies (spec: auth).

- ``CurrentCaller``  — any valid token
- ``EntitledCaller`` — valid + `mnemosyne` entitlement (or admin)
- ``AdminCaller``    — valid + `is_admin` or `mnemosyne:admin` scope
"""

from typing import Annotated, cast

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.application.audit import AuditService
from app.config import get_settings
from app.domain.ports.auth_port import AuthPort, AuthUnavailableError, TokenInvalidError
from app.domain.services.org_scope import set_allowed_organizations
from app.domain.value_objects.identity import CallerIdentity
from app.interfaces.api.errors import (
    ForbiddenError,
    UnauthenticatedError,
    UpstreamUnavailableError,
)

bearer_scheme = HTTPBearer(auto_error=False)


def get_auth_port(request: Request) -> AuthPort:
    return cast(AuthPort, request.app.state.auth_port)


def get_audit_service(request: Request) -> AuditService:
    return cast(AuditService, request.app.state.audit_service)


async def get_current_caller(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    auth_port: Annotated[AuthPort, Depends(get_auth_port)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
) -> CallerIdentity:
    if credentials is None or not credentials.credentials:
        raise UnauthenticatedError("missing bearer token")
    try:
        return await auth_port.verify(credentials.credentials)
    except TokenInvalidError as exc:
        await audit.record_denied(None, f"auth.{request.method} {request.url.path}")
        raise UnauthenticatedError("invalid token") from exc
    except AuthUnavailableError as exc:
        raise UpstreamUnavailableError("authentication service unavailable") from exc


CurrentCaller = Annotated[CallerIdentity, Depends(get_current_caller)]


async def get_entitled_caller(
    request: Request,
    caller: CurrentCaller,
    audit: Annotated[AuditService, Depends(get_audit_service)],
) -> CallerIdentity:
    settings = get_settings()
    if not caller.can_access(settings.required_entitlement, settings.service_audience):
        await audit.record_denied(caller, f"access.{request.method} {request.url.path}")
        raise ForbiddenError(
            f"missing required entitlement '{settings.required_entitlement}'",
            code="missing_entitlement",
        )
    # Scope all repository reads for this request to the caller's accessible orgs
    # (None = unrestricted). Task-local, so it never leaks across requests.
    set_allowed_organizations(caller.allowed_organizations(settings.required_entitlement))
    return caller


EntitledCaller = Annotated[CallerIdentity, Depends(get_entitled_caller)]


async def get_admin_caller(
    request: Request,
    caller: EntitledCaller,
    audit: Annotated[AuditService, Depends(get_audit_service)],
) -> CallerIdentity:
    settings = get_settings()
    if not caller.can_administer(settings.admin_scope):
        await audit.record_denied(caller, f"admin.{request.method} {request.url.path}")
        raise ForbiddenError("administrator privileges required", code="admin_required")
    return caller


AdminCaller = Annotated[CallerIdentity, Depends(get_admin_caller)]
