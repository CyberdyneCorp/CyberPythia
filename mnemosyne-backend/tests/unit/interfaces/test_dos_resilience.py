"""DoS-resilience regression tests (spec: rest-api; CWE-770).

Covers the three hardening measures added for issues #56/#59/#60:
  * bounded ``limit`` query params (reject values above MAX_PAGE_SIZE with 422);
  * a webhook body-size cap enforced with 413 before signature processing;
  * per-caller/IP rate limiting that returns 429 with Retry-After.
"""

import json as _json

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.interfaces.api.rate_limit import limiter
from app.interfaces.api.schemas.schemas import MAX_PAGE_SIZE
from app.main import create_app
from tests.unit.interfaces.test_api_endpoints import build_fake_container, seed_repo, user


@pytest.fixture
def container():
    return build_fake_container()


def _client(container) -> AsyncClient:
    app = create_app(container)
    app.state.auth_port = container.auth_port
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


class TestBoundedLimits:
    """#60 — user-supplied ``limit`` params must be clamped to MAX_PAGE_SIZE."""

    async def test_intelligence_search_limit_above_cap_rejected(self, container):
        async with _client(container) as c:
            resp = await c.get(
                "/api/v1/intelligence/search",
                params={"query": "x", "limit": MAX_PAGE_SIZE + 1},
                headers=user(),
            )
        assert resp.status_code == 422

    async def test_intelligence_memories_limit_above_cap_rejected(self, container):
        async with _client(container) as c:
            resp = await c.get(
                "/api/v1/intelligence/organizations/cyberdyne/memories",
                params={"limit": 10_000},
                headers=user(),
            )
        assert resp.status_code == 422

    async def test_repo_memories_limit_above_cap_rejected(self, container):
        repo = await seed_repo(container)
        async with _client(container) as c:
            resp = await c.get(
                f"/api/v1/repos/{repo.id}/memories",
                params={"limit": MAX_PAGE_SIZE + 1},
                headers=user(),
            )
        assert resp.status_code == 422

    async def test_limit_within_cap_accepted(self, container):
        async with _client(container) as c:
            resp = await c.get(
                "/api/v1/intelligence/search",
                params={"query": "x", "limit": MAX_PAGE_SIZE},
                headers=user(),
            )
        assert resp.status_code == 200


class TestWebhookBodyCap:
    """#59 — oversized webhook payloads are rejected before parsing/signature."""

    @pytest.fixture(autouse=True)
    def _small_cap(self, monkeypatch):
        monkeypatch.setenv("WEBHOOK_MAX_BODY_BYTES", "1024")
        get_settings.cache_clear()
        yield
        get_settings.cache_clear()

    async def test_oversized_body_rejected_with_413(self, container):
        # A >1KB body with a bogus signature: a 413 (not 401) proves the size
        # check runs before signature verification and before json parsing.
        body = _json.dumps({"installation": {"id": 99}, "pad": "A" * 2048}).encode()
        assert len(body) > 1024
        async with _client(container) as c:
            resp = await c.post(
                "/api/v1/webhooks/github",
                content=body,
                headers={
                    "X-Hub-Signature-256": "sha256=deadbeef",
                    "X-GitHub-Event": "push",
                    "X-GitHub-Delivery": "oversized-1",
                },
            )
        assert resp.status_code == 413
        # Nothing was recorded/dispatched to processing.
        assert container.webhook_deliveries.seen == {}

    async def test_declared_content_length_over_cap_rejected(self, container):
        async with _client(container) as c:
            resp = await c.post(
                "/api/v1/webhooks/github",
                content=b"{}",
                headers={"Content-Length": "5000", "X-GitHub-Event": "push"},
            )
        assert resp.status_code == 413

    async def test_small_body_still_processed_normally(self, container):
        # Under the cap: falls through to signature verification (401, not 413).
        body = _json.dumps({"installation": {"id": 99}}).encode()
        async with _client(container) as c:
            resp = await c.post(
                "/api/v1/webhooks/github",
                content=body,
                headers={
                    "X-Hub-Signature-256": "sha256=deadbeef",
                    "X-GitHub-Event": "push",
                    "X-GitHub-Delivery": "small-1",
                },
            )
        assert resp.status_code == 401


class TestRateLimiting:
    """#56 — exceeding the configured rate limit returns 429 + Retry-After."""

    @pytest.fixture(autouse=True)
    def _tight_limits(self, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
        monkeypatch.setenv("RATE_LIMIT_HEALTH", "1/minute")
        get_settings.cache_clear()
        limiter.reset()
        yield
        get_settings.cache_clear()
        limiter.reset()

    async def test_health_rate_limited_after_one_call(self, container):
        async with _client(container) as c:
            first = await c.get("/api/v1/health")
            second = await c.get("/api/v1/health")
        assert first.status_code == 200
        assert second.status_code == 429
        assert second.json()["error"]["code"] == "rate_limited"
        assert "retry-after" in {k.lower() for k in second.headers}
