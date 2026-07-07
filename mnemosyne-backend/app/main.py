"""FastAPI application entrypoint (design D4)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.composition import Container, build_container
from app.interfaces.api.errors import register_error_handlers
from app.interfaces.api.routers import github, health, repositories


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
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

    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(github.router)
    app.include_router(repositories.router)
    return app


app = create_app()
