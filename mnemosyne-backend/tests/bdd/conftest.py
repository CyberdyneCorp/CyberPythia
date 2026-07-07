"""BDD harness (spec: quality; tasks 9.1/9.2).

Local mode (default): starts mock CyberdyneAuth+GitHub fixtures, then the real
Mnemosyne API + worker as subprocesses against the compose Postgres/Redis/MinIO.

Staging mode (`--server-url https://...`): runs against a deployed server and
acquires a real CyberdyneAuth client-credentials token from the environment
(STAGING_AUTH_CLIENT_ID / STAGING_AUTH_CLIENT_SECRET / STAGING_AUTH_ISSUER).
"""

import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

BACKEND_DIR = Path(__file__).parents[2]
API_PORT = 8001
MCP_PORT = 8101
MOCK_PORT = 8765

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://mnemosyne:mnemosyne@localhost:5433/mnemosyne"
)
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/1")
MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "localhost:9000")


def pytest_addoption(parser):
    parser.addoption(
        "--server-url",
        action="store",
        default=None,
        help="Run BDD against this deployed server instead of a local stack",
    )


def pytest_collection_modifyitems(config, items):
    for item in items:
        if "bdd" in str(item.fspath):
            item.add_marker(pytest.mark.bdd)


@pytest.fixture(scope="session")
def staging_url(request):
    return request.config.getoption("--server-url")


@pytest.fixture(scope="session")
def mock_services(staging_url):
    if staging_url:
        yield None
        return
    from tests.bdd.mock_services import DEMO_FIXTURE, MockServices

    services = MockServices(port=MOCK_PORT)
    services.fixture.update(DEMO_FIXTURE)
    services.start()
    yield services
    services.stop()


def _stack_env(mock) -> dict[str, str]:
    return {
        **os.environ,
        "APP_ENV": "test",
        "DATABASE_URL": DATABASE_URL,
        "REDIS_URL": REDIS_URL,
        "MINIO_ENDPOINT": MINIO_ENDPOINT,
        "MINIO_ACCESS_KEY": "mnemosyne",
        "MINIO_SECRET_KEY": "mnemosyne-secret",
        "MINIO_BUCKET": "mnemosyne-bdd",
        "CYBERDYNEAUTH_ISSUER": mock.issuer,
        "AUTH_VALIDATION_MODE": "jwks",
        "GITHUB_API_BASE_URL": mock.github_base,
        "TOKEN_ENCRYPTION_KEY": "8Fbp2VYZbYSbi77Yv6y0kJ0hE-pO_TB0aq1V1jXcCAU=",
        "MCP_PORT": str(MCP_PORT),
        "OPENAI_API_KEY": "",
        "EMBEDDING_MODEL": "test",
    }


def _wait_tcp(host: str, port: int, timeout: float = 30) -> None:
    import socket

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2):
                return
        except OSError:
            time.sleep(0.3)
    raise RuntimeError(f"nothing listening on {host}:{port}")


def _wait_http(url: str, timeout: float = 30) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            response = httpx.get(url, timeout=2)
            if response.status_code < 500:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.3)
    raise RuntimeError(f"server at {url} did not come up")


@pytest.fixture(scope="session")
def server_url(staging_url, mock_services):
    """Base URL of the API under test; local mode boots the whole stack."""
    if staging_url:
        yield staging_url.rstrip("/")
        return

    env = _stack_env(mock_services)

    import asyncio

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.infrastructure.persistence.models import Base

    async def reset_db():
        engine = create_async_engine(DATABASE_URL)
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(Base.metadata.create_all)
            tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
            await conn.execute(text(f"TRUNCATE {tables} CASCADE"))
        await engine.dispose()

    asyncio.run(reset_db())

    log_dir = BACKEND_DIR / ".bdd-logs"
    log_dir.mkdir(exist_ok=True)

    def spawn(name: str, *args: str) -> subprocess.Popen:
        log = (log_dir / f"{name}.log").open("w")
        return subprocess.Popen(
            [sys.executable, "-m", *args],
            cwd=BACKEND_DIR,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )

    api = spawn("api", "uvicorn", "app.main:app", "--port", str(API_PORT))
    worker = spawn("worker", "arq", "app.infrastructure.queue.worker.WorkerSettings")
    mcp = spawn("mcp", "app.interfaces.mcp.server")
    try:
        _wait_http(f"http://127.0.0.1:{API_PORT}/api/v1/health")
        _wait_tcp("127.0.0.1", MCP_PORT)
        yield f"http://127.0.0.1:{API_PORT}"
    finally:
        for proc in (api, worker, mcp):
            proc.terminate()
        for proc in (api, worker, mcp):
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


@pytest.fixture(scope="session")
def mcp_url(staging_url, server_url):
    if staging_url:
        return os.environ.get("STAGING_MCP_URL", staging_url.replace("api", "mcp"))
    return f"http://127.0.0.1:{MCP_PORT}"


def _staging_token() -> str:
    issuer = os.environ["STAGING_AUTH_ISSUER"]
    response = httpx.post(
        f"{issuer}/api/v1/auth/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_id": os.environ["STAGING_AUTH_CLIENT_ID"],
            "client_secret": os.environ["STAGING_AUTH_CLIENT_SECRET"],
        },
        timeout=15,
    )
    response.raise_for_status()
    return response.json()["access_token"]


@pytest.fixture(scope="session")
def admin_token(staging_url, mock_services):
    if staging_url:
        return _staging_token()  # staging client must hold admin + entitlement
    return mock_services.mint_token("bdd-admin", is_admin=True)


@pytest.fixture(scope="session")
def user_token(staging_url, mock_services):
    if staging_url:
        return _staging_token()
    return mock_services.mint_token("bdd-user")


@pytest.fixture(scope="session")
def unentitled_token(staging_url, mock_services):
    if staging_url:
        pytest.skip("unentitled-token scenarios run in local mode only")
    return mock_services.mint_token("bdd-outsider", entitlements=[])


@pytest.fixture
def api(server_url, user_token):
    with httpx.Client(
        base_url=server_url, headers={"Authorization": f"Bearer {user_token}"}, timeout=30
    ) as client:
        yield client


@pytest.fixture
def admin_api(server_url, admin_token):
    with httpx.Client(
        base_url=server_url, headers={"Authorization": f"Bearer {admin_token}"}, timeout=30
    ) as client:
        yield client
