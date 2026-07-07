"""Unit tests for GitHubAppAuth (RSA key + respx-mocked token endpoint)."""

import time

import httpx
import pytest
import respx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.domain.ports.github_app_port import GitHubAppError
from app.infrastructure.github.app_auth import API_BASE, GitHubAppAuth


@pytest.fixture(scope="module")
def private_key_pem():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()


def _future(seconds: int) -> str:
    from datetime import UTC, datetime, timedelta

    return (datetime.now(UTC) + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


@respx.mock
async def test_mints_installation_token(private_key_pem):
    route = respx.post(f"{API_BASE}/app/installations/99/access_tokens").respond(
        201, json={"token": "ghs_abc", "expires_at": _future(3600)}
    )
    auth = GitHubAppAuth()
    token = await auth.installation_token("12345", "99", private_key_pem)
    assert token == "ghs_abc"
    # the app JWT was sent as a bearer
    assert route.calls[0].request.headers["Authorization"].startswith("Bearer ")


@respx.mock
async def test_caches_token_until_near_expiry(private_key_pem):
    route = respx.post(f"{API_BASE}/app/installations/99/access_tokens").respond(
        201, json={"token": "ghs_abc", "expires_at": _future(3600)}
    )
    auth = GitHubAppAuth()
    await auth.installation_token("12345", "99", private_key_pem)
    await auth.installation_token("12345", "99", private_key_pem)
    assert route.call_count == 1  # cached


@respx.mock
async def test_refreshes_when_expired(private_key_pem):
    route = respx.post(f"{API_BASE}/app/installations/99/access_tokens").respond(
        201, json={"token": "ghs_abc", "expires_at": _future(30)}  # inside refresh margin
    )
    auth = GitHubAppAuth()
    await auth.installation_token("12345", "99", private_key_pem)
    await auth.installation_token("12345", "99", private_key_pem)
    assert route.call_count == 2  # re-minted


@respx.mock
async def test_github_rejection_raises(private_key_pem):
    respx.post(f"{API_BASE}/app/installations/99/access_tokens").respond(404)
    with pytest.raises(GitHubAppError):
        await GitHubAppAuth().installation_token("12345", "99", private_key_pem)


async def test_invalid_private_key_raises():
    with pytest.raises(GitHubAppError):
        await GitHubAppAuth().installation_token("12345", "99", "not-a-key")


@respx.mock
async def test_network_error_raises(private_key_pem):
    respx.post(f"{API_BASE}/app/installations/99/access_tokens").mock(
        side_effect=httpx.ConnectError("down")
    )
    with pytest.raises(GitHubAppError):
        await GitHubAppAuth().installation_token("12345", "99", private_key_pem)


@respx.mock
async def test_missing_expires_at_defaults(private_key_pem):
    respx.post(f"{API_BASE}/app/installations/99/access_tokens").respond(
        201, json={"token": "ghs_abc"}
    )
    auth = GitHubAppAuth()
    token = await auth.installation_token("12345", "99", private_key_pem)
    assert token == "ghs_abc"
    assert auth._cache["99"][1] > time.time()  # a default expiry was set
