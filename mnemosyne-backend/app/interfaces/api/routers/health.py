"""Health endpoints (spec: rest-api).

The public probe is unauthenticated and returns only an overall status so it
leaks no per-dependency reachability or failing exception classes (CWE-200). The
detailed per-component checks are available on the admin-gated endpoint.
"""

from fastapi import APIRouter, Request
from sqlalchemy import text

from app.interfaces.api.rate_limit import health_limit, limiter
from app.interfaces.api.security import AdminCaller

router = APIRouter(prefix="/api/v1", tags=["health"])
admin_router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


async def _component_checks(request: Request) -> dict[str, str]:
    container = request.app.state.container
    checks: dict[str, str] = {}

    try:
        async with container.session_factory() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {type(exc).__name__}"

    try:
        await container.sync_lock._redis.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {type(exc).__name__}"

    try:
        import asyncio

        await asyncio.to_thread(
            container.storage._client.bucket_exists,
            container.settings.minio_bucket,
        )
        checks["object_storage"] = "ok"
    except Exception as exc:
        checks["object_storage"] = f"error: {type(exc).__name__}"

    return checks


def _overall_status(checks: dict[str, str]) -> str:
    return "ok" if all(v == "ok" for v in checks.values()) else "degraded"


@router.get("/health")
@limiter.limit(health_limit)
async def health(request: Request) -> dict[str, str]:
    # Public probe: overall status only. Kept at HTTP 200 while serving so the
    # container/rollout healthcheck contract (docs/deploy-coolify.md) holds; the
    # per-dependency detail is admin-only (CWE-200).
    checks = await _component_checks(request)
    return {"status": _overall_status(checks)}


@admin_router.get("/health")
async def admin_health(request: Request, caller: AdminCaller) -> dict[str, object]:
    checks = await _component_checks(request)
    return {"status": _overall_status(checks), "checks": checks}
