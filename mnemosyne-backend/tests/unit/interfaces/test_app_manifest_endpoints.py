"""Interface tests for the GitHub App manifest onboarding endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.application.use_cases.github_connections import GitHubConnectionUseCases
from app.main import create_app
from tests.unit.application.fakes import FakeCipher, FakeGitHubAppAuth
from tests.unit.interfaces.test_api_endpoints import admin, build_fake_container, user

SECRET = "endpoint-secret"


@pytest.fixture
def container():
    c = build_fake_container()
    # connection use cases with App-manifest support enabled
    c.connection_use_cases = GitHubConnectionUseCases(
        c.connections, c.github, FakeCipher(), app_auth=FakeGitHubAppAuth(),
        public_api_base_url="https://api.example.ai",
        github_web_base_url="https://github.com", state_secret=SECRET,
    )
    return c


@pytest.fixture
def client(container):
    app = create_app(container)
    app.state.auth_port = container.auth_port
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test",
                       follow_redirects=False)


async def _state(client) -> str:
    r = await client.get("/api/v1/github/app/manifest?organization=cyberdyne", headers=admin())
    return r.json()["state"]


class TestManifestEndpoints:
    async def test_manifest_bootstrap(self, client):
        async with client:
            r = await client.get(
                "/api/v1/github/app/manifest?organization=cyberdyne", headers=admin()
            )
        assert r.status_code == 200
        body = r.json()
        assert body["post_url"].startswith("https://github.com/organizations/cyberdyne/")
        assert body["manifest"]["default_permissions"]["contents"] == "read"
        assert body["state"]

    async def test_manifest_requires_admin(self, client):
        async with client:
            r = await client.get(
                "/api/v1/github/app/manifest?organization=cyberdyne", headers=user()
            )
        assert r.status_code == 403

    async def test_manifest_callback_redirects_to_install(self, client):
        async with client:
            state = await _state(client)
            r = await client.get(
                f"/api/v1/github/app/manifest-callback?code=abc&state={state}"
            )
        assert r.status_code == 303
        assert r.headers["location"].endswith("/installations/new")

    async def test_setup_redirects_to_dashboard(self, client):
        async with client:
            state = await _state(client)
            await client.get(f"/api/v1/github/app/manifest-callback?code=abc&state={state}")
            r = await client.get(
                f"/api/v1/github/app/setup?installation_id=999&state={state}"
            )
        assert r.status_code == 303
        assert "app_connected=1" in r.headers["location"]

    async def test_callback_bad_state_redirects_with_error(self, client):
        async with client:
            r = await client.get(
                "/api/v1/github/app/manifest-callback?code=abc&state=bogus.state"
            )
        assert r.status_code == 303
        assert "app_error=" in r.headers["location"]
