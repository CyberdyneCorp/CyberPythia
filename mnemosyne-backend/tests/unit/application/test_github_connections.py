"""Unit tests for GitHub credential lifecycle use cases (spec: github-connection)."""

from uuid import uuid4

import pytest

from app.application.errors import (
    InvalidCredentialError,
    MissingPermissionsError,
    UnknownResourceError,
)
from app.application.use_cases.github_connections import GitHubConnectionUseCases
from tests.unit.application.fakes import FakeCipher, FakeConnectionPort, FakeGitHub


@pytest.fixture
def github():
    return FakeGitHub()


@pytest.fixture
def connections():
    return FakeConnectionPort()


@pytest.fixture
def use_cases(connections, github):
    return GitHubConnectionUseCases(connections, github, FakeCipher())


async def test_connect_valid_pat(use_cases, connections):
    view = await use_cases.connect("ghp_secret_ab12")
    assert view.owner == "cyberdyne"
    assert view.token_hint == "ab12"
    assert "contents" in view.permissions

    stored = await connections.get(view.id)
    assert stored.encrypted_token == b"enc:ghp_secret_ab12"  # encrypted at rest


async def test_connect_missing_permissions_not_persisted(use_cases, connections, github):
    github.token_info = github.token_info.__class__(
        login="cyberdyne", owner_type="Organization", permissions={"contents", "metadata"}
    )
    with pytest.raises(MissingPermissionsError) as exc:
        await use_cases.connect("ghp_x")
    assert exc.value.missing == ["issues", "pull_requests"]
    assert not connections.items


async def test_connect_invalid_pat_not_persisted(use_cases, connections, github):
    github.auth_fails = True
    with pytest.raises(InvalidCredentialError):
        await use_cases.connect("ghp_bad")
    assert not connections.items


async def test_connect_rotation_replaces_credential_same_id(use_cases, connections):
    first = await use_cases.connect("ghp_old_1111")
    second = await use_cases.connect("ghp_new_2222")
    assert first.id == second.id  # same owner -> rotation, not duplication
    stored = await connections.get(second.id)
    assert stored.encrypted_token == b"enc:ghp_new_2222"
    assert stored.token_hint == "2222"


async def test_view_never_contains_credential(use_cases):
    view = await use_cases.connect("ghp_secret_ab12")
    assert "ghp_secret" not in str(view)


async def test_test_healthy_connection(use_cases):
    view = await use_cases.connect("ghp_secret_ab12")
    result = await use_cases.test(view.id)
    assert result["ok"] is True
    assert result["rate_limit"]["remaining"] == 4999


async def test_test_revoked_credential_marks_broken(use_cases, github, connections):
    view = await use_cases.connect("ghp_secret_ab12")
    github.auth_fails = True
    result = await use_cases.test(view.id)
    assert result == {"ok": False, "status": "broken"}
    assert (await connections.get(view.id)).status.value == "broken"


async def test_test_recovers_broken_connection(use_cases, github, connections):
    view = await use_cases.connect("ghp_secret_ab12")
    github.auth_fails = True
    await use_cases.test(view.id)
    github.auth_fails = False
    result = await use_cases.test(view.id)
    assert result["ok"] is True
    assert (await connections.get(view.id)).status.value == "active"


async def test_test_unknown_connection(use_cases):
    with pytest.raises(UnknownResourceError):
        await use_cases.test(uuid4())


async def test_delete(use_cases, connections):
    view = await use_cases.connect("ghp_secret_ab12")
    await use_cases.delete(view.id)
    assert not connections.items
    with pytest.raises(UnknownResourceError):
        await use_cases.delete(view.id)


async def test_credential_for_internal_use(use_cases):
    view = await use_cases.connect("ghp_secret_ab12")
    assert await use_cases.credential_for(view.id) == "ghp_secret_ab12"
