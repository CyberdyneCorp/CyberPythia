"""Unauthenticated health endpoint (spec: rest-api)."""

from fastapi import APIRouter, Request
from sqlalchemy import text

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health")
async def health(request: Request) -> dict[str, object]:
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

    status = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": status, "checks": checks}
