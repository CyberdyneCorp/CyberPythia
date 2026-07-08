"""Unit tests for MCP one-click OAuth wiring (spec: mcp-interface, auth).

Covers the composite token verifier (which keeps API keys + bearers working
alongside OAuth), the proxy builder, and build_mcp's feature flag.
"""

import pytest

from app.config import Settings
from app.domain.ports.auth_port import AuthUnavailableError, TokenInvalidError
from app.domain.value_objects.identity import CallerIdentity
from app.interfaces.mcp.oauth import (
    CALLER_CLAIM,
    CompositeTokenVerifier,
    build_oauth_proxy,
    caller_from_access_token,
)
from app.interfaces.mcp.server import build_mcp
from tests.unit.interfaces.test_api_endpoints import build_fake_container


class FakeAuthPort:
    """Resolves `mnem_ok`/`good` to an entitled user, `agent` to a service token."""

    async def verify(self, token: str) -> CallerIdentity:
        if token == "down":
            raise AuthUnavailableError("auth plane down")
        if token in ("mnem_ok", "good"):
            return CallerIdentity(subject="user-1", entitlements=frozenset({"mnemosyne"}))
        if token == "agent":
            return CallerIdentity(subject="svc-1", audiences=frozenset({"mnemosyne"}))
        if token == "unentitled":
            return CallerIdentity(subject="x", entitlements=frozenset({"other"}))
        raise TokenInvalidError("invalid")


def _verifier() -> CompositeTokenVerifier:
    return CompositeTokenVerifier(
        FakeAuthPort(), required_entitlement="mnemosyne", service_audience="mnemosyne"
    )


def _oauth_settings(**over) -> Settings:
    base = dict(
        mcp_oauth_enabled=True,
        mcp_oauth_public_base_url="https://mnemosyne.mcp.example.ai",
        mcp_oauth_client_id="cyb_mcp",
        mcp_oauth_client_secret="s3cret",
    )
    base.update(over)
    return Settings(**base)  # type: ignore[arg-type]


class TestCompositeTokenVerifier:
    async def test_api_key_token_yields_access_token_with_caller(self):
        access = await _verifier().verify_token("mnem_ok")
        assert access is not None
        assert access.subject == "user-1"
        caller = caller_from_access_token(access)
        assert caller is not None and caller.has_entitlement("mnemosyne")
        assert access.claims[CALLER_CLAIM] is caller

    async def test_service_audience_token_accepted(self):
        access = await _verifier().verify_token("agent")
        assert access is not None and access.subject == "svc-1"

    async def test_invalid_token_returns_none(self):
        assert await _verifier().verify_token("nope") is None

    async def test_auth_unavailable_returns_none(self):
        assert await _verifier().verify_token("down") is None

    async def test_unentitled_returns_none(self):
        assert await _verifier().verify_token("unentitled") is None

    def test_caller_from_missing_token_is_none(self):
        assert caller_from_access_token(None) is None


class TestBuildOAuthProxy:
    def test_builds_with_derived_upstream_endpoints(self):
        settings = _oauth_settings()
        proxy = build_oauth_proxy(FakeAuthPort(), settings)
        assert proxy is not None
        # derived from the CyberdyneAuth issuer
        assert settings.mcp_oauth_upstream_authorize_url.endswith("/oauth2/authorize")
        assert settings.mcp_oauth_upstream_token_url.endswith("/oauth2/token")

    def test_requires_base_url(self):
        with pytest.raises(ValueError, match="public_base_url"):
            build_oauth_proxy(FakeAuthPort(), _oauth_settings(mcp_oauth_public_base_url=""))

    def test_requires_client_credentials(self):
        with pytest.raises(ValueError, match="client_id/secret"):
            build_oauth_proxy(FakeAuthPort(), _oauth_settings(mcp_oauth_client_secret=""))


class TestBuildMcpFeatureFlag:
    def test_oauth_disabled_by_default(self, monkeypatch):
        # default settings → flag off → no auth provider (today's behavior)
        assert build_mcp(build_fake_container()).auth is None

    def test_oauth_enabled_attaches_provider(self, monkeypatch):
        import app.interfaces.mcp.server as server

        monkeypatch.setattr(server, "get_settings", _oauth_settings)
        container = build_fake_container()
        container.auth_port = FakeAuthPort()
        mcp = build_mcp(container)
        assert mcp.auth is not None


def _route_paths(app) -> set[str]:
    paths: set[str] = set()

    def walk(routes, prefix=""):
        for r in routes:
            p = prefix + getattr(r, "path", "")
            if getattr(r, "routes", None):
                walk(r.routes, p)
            else:
                paths.add(p)

    walk(app.routes)
    return paths


_OAUTH_ROUTES = {
    "/.well-known/oauth-authorization-server",
    "/.well-known/oauth-protected-resource/mcp",  # RFC 9728: path-suffixed to the resource
    "/register",  # dynamic client registration (DCR)
    "/authorize",
    "/token",
    "/auth/callback",
}


class TestOAuthSurface:
    def test_endpoints_served_when_enabled(self, monkeypatch):
        import app.interfaces.mcp.server as server

        monkeypatch.setattr(server, "get_settings", _oauth_settings)
        container = build_fake_container()
        container.auth_port = FakeAuthPort()
        paths = _route_paths(build_mcp(container).http_app())
        assert paths >= _OAUTH_ROUTES

    def test_no_oauth_endpoints_when_disabled(self):
        # default settings → flag off → none of the OAuth routes exist
        paths = _route_paths(build_mcp(build_fake_container()).http_app())
        assert not (_OAUTH_ROUTES & paths)
