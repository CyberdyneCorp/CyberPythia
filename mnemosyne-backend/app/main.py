"""FastAPI application entrypoint (design D4)."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.composition import Container, build_container
from app.config import get_settings
from app.interfaces.api.errors import register_error_handlers
from app.interfaces.api.rate_limit import limiter, rate_limit_exceeded_handler
from app.interfaces.api.routers import (
    api_keys,
    github,
    health,
    intelligence,
    repositories,
    webhooks,
)

logger = logging.getLogger(__name__)


async def _run_migrations() -> None:
    """Apply Alembic migrations to head. Run in a thread: migrations/env.py uses
    asyncio.run(), which can't be called from the already-running event loop."""

    def _upgrade() -> None:
        from alembic import command
        from alembic.config import Config

        command.upgrade(Config("alembic.ini"), "head")

    await asyncio.to_thread(_upgrade)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    if get_settings().run_migrations_on_boot:
        logger.info("applying database migrations (alembic upgrade head)")
        await _run_migrations()
    yield
    container: Container = app.state.container
    await container.queue.close()
    await container.sync_lock.close()
    await container.github.close()


def create_app(container: Container | None = None) -> FastAPI:
    app = FastAPI(
        title="Mnemosyne",
        description="GitHub context & memory layer for AI agents and humans.",
        version="0.1.0",
        lifespan=lifespan,
    )
    container = container or build_container()
    app.state.container = container
    app.state.auth_port = container.auth_port
    app.state.audit_service = container.audit_service

    # Rate limiting (spec: rest-api; CWE-770). The limiter is a module-level
    # singleton so route decorators bind at import; its enabled flag mirrors the
    # current settings, letting tests disable it or tighten limits per case.
    limiter.enabled = get_settings().rate_limit_enabled
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)  # type: ignore[arg-type]
    app.add_middleware(SlowAPIMiddleware)

    origins = [o.strip() for o in get_settings().cors_allowed_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        max_age=3600,
    )

    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(health.admin_router)
    app.include_router(github.router)
    app.include_router(github.admin_router)
    app.include_router(repositories.router)
    app.include_router(intelligence.router)
    app.include_router(webhooks.router)
    app.include_router(api_keys.router)
    return app


app = create_app()
