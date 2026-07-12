"""Unit tests for GitHub App connections (spec: github-app / github-connection)."""

import pytest

from app.application.errors import InvalidCredentialError
from app.application.use_cases.github_connections import GitHubConnectionUseCases
from app.domain.value_objects.enums import ConnectionKind
from tests.unit.application.fakes import (
    FakeCipher,
    FakeConnectionPort,
    FakeGitHub,
    FakeGitHubAppAuth,
)


@pytest.fixture
def env():
    github = FakeGitHub()
    connections = FakeConnectionPort()
    app_auth = FakeGitHubAppAuth()
    uc = GitHubConnectionUseCases(connections, github, FakeCipher(), app_auth=app_auth)
    return uc, connections, github, app_auth


async def test_connect_app_persists_encrypted_app_connection(env):
    uc, connections, _, _ = env
    view = await uc.connect_app("12345", "99", "-----BEGIN PRIVATE KEY-----\n...", "whsec")
    assert view.kind == "github_app"
    assert view.installation_id == "99"

    stored = await connections.get(view.id)
    assert stored.kind is ConnectionKind.GITHUB_APP
    assert stored.encrypted_private_key == b"enc:-----BEGIN PRIVATE KEY-----\n..."
    assert stored.encrypted_webhook_secret == b"enc:whsec"
    assert stored.encrypted_token is None


async def test_connect_app_invalid_credentials_not_persisted(env):
    uc, connections, _, app_auth = env
    app_auth.fails = True
    with pytest.raises(InvalidCredentialError):
        await uc.connect_app("12345", "99", "bad", "whsec")
    assert not connections.items


async def test_app_view_never_leaks_secrets(env):
    uc, *_ = env
    view = await uc.connect_app("12345", "99", "PRIVATE", "whsec")
    assert "PRIVATE" not in str(view) and "whsec" not in str(view)


async def test_credential_for_mints_installation_token(env):
    uc, _, _, app_auth = env
    view = await uc.connect_app("12345", "99", "PRIVATE", "whsec")
    token = await uc.credential_for(view.id)
    assert token == "ghs_inst_99"
    assert app_auth.calls >= 1


async def test_webhook_secret_lookup_by_installation(env):
    uc, *_ = env
    await uc.connect_app("12345", "77", "PRIVATE", "the-secret")
    assert await uc.webhook_secret_for_installation("77") == "the-secret"
    assert await uc.webhook_secret_for_installation("nope") is None


async def test_connect_app_rejects_empty_webhook_secret(env):
    """#67 (CWE-347): an empty/blank webhook secret is not a usable HMAC key."""
    uc, connections, _, _ = env
    for blank in ("", "   "):
        with pytest.raises(InvalidCredentialError):
            await uc.connect_app("12345", "99", "PRIVATE", blank)
    assert not connections.items


async def test_empty_stored_webhook_secret_treated_as_no_secret(env):
    """#67 (CWE-347): a connection whose stored secret is blank must not verify a
    delivery — the lookup returns None so the webhook receiver 401s."""
    from datetime import UTC, datetime
    from uuid import uuid4

    from app.domain.entities.github_connection import GitHubConnection
    from app.domain.value_objects.enums import ConnectionKind

    uc, connections, _, _ = env
    cipher = FakeCipher()
    now = datetime.now(UTC)
    # A legacy/tampered connection persisted with an empty webhook secret.
    connections.items[uuid4()] = GitHubConnection(
        id=uuid4(),
        owner="cyberdyne",
        owner_type="Organization",
        kind=ConnectionKind.GITHUB_APP,
        app_id="1",
        installation_id="88",
        encrypted_webhook_secret=cipher.encrypt(""),
        created_at=now,
        updated_at=now,
    )
    assert await uc.webhook_secret_for_installation("88") is None


async def test_test_app_connection_health(env):
    uc, _, _, app_auth = env
    view = await uc.connect_app("12345", "99", "PRIVATE", "whsec")
    result = await uc.test(view.id)
    assert result["ok"] is True

    app_auth.fails = True
    broken = await uc.test(view.id)
    assert broken == {"ok": False, "status": "broken"}
