"""Unit tests for GitHub App manifest onboarding use cases (spec: github-connection)."""

import pytest

from app.application.errors import InvalidCredentialError
from app.application.use_cases.github_connections import GitHubConnectionUseCases
from app.domain.services.signed_state import InvalidStateError
from app.domain.value_objects.enums import ConnectionKind, ConnectionStatus
from tests.unit.application.fakes import (
    FakeCipher,
    FakeConnectionPort,
    FakeGitHub,
    FakeGitHubAppAuth,
)

SECRET = "hmac-secret"


def _uc(app_auth=None) -> GitHubConnectionUseCases:
    return GitHubConnectionUseCases(
        FakeConnectionPort(), FakeGitHub(), FakeCipher(),
        app_auth=app_auth if app_auth is not None else FakeGitHubAppAuth(),
        public_api_base_url="https://api.example.ai",
        github_web_base_url="https://github.com",
        state_secret=SECRET,
    )


def test_build_manifest_shape_and_urls():
    uc = _uc()
    manifest, post_url, state = uc.build_app_manifest("CyberdyneCorp", "admin-1")
    assert manifest["default_permissions"] == {
        "contents": "read", "issues": "read", "pull_requests": "read", "metadata": "read"
    }
    assert manifest["hook_attributes"]["url"] == "https://api.example.ai/api/v1/webhooks/github"
    assert manifest["redirect_url"].endswith("/api/v1/github/app/manifest-callback")
    assert f"state={state}" in str(manifest["setup_url"])  # baked for the setup redirect
    assert post_url.startswith("https://github.com/organizations/CyberdyneCorp/settings/apps/new")


async def test_complete_manifest_persists_pending_connection():
    uc = _uc()
    _m, _p, state = uc.build_app_manifest("cyberdyne", "admin-1")
    view, install_url = await uc.complete_manifest("code123", state)
    assert view.status == ConnectionStatus.PENDING_INSTALLATION.value
    assert view.kind == ConnectionKind.GITHUB_APP.value
    assert install_url == "https://github.com/apps/mnemosyne-cyberdyne/installations/new"


async def test_complete_setup_activates_connection():
    uc = _uc()
    _m, _p, state = uc.build_app_manifest("cyberdyne", "admin-1")
    await uc.complete_manifest("code123", state)
    view = await uc.complete_setup("55555", state)
    assert view.status == ConnectionStatus.ACTIVE.value
    assert view.installation_id == "55555"
    assert set(view.permissions) == {"contents", "issues", "pull_requests", "metadata"}


async def test_bad_state_rejected():
    uc = _uc()
    with pytest.raises(InvalidStateError):
        await uc.complete_manifest("code", "tampered.state")


async def test_setup_without_pending_connection():
    from app.application.errors import UnknownResourceError

    uc = _uc()
    _m, _p, state = uc.build_app_manifest("ghost-org", "admin-1")
    with pytest.raises(UnknownResourceError):
        await uc.complete_setup("1", state)


async def test_manifest_conversion_failure_surfaces():
    failing = FakeGitHubAppAuth()
    failing.fails = True
    uc = _uc(app_auth=failing)
    _m, _p, state = uc.build_app_manifest("cyberdyne", "admin-1")
    with pytest.raises(InvalidCredentialError):
        await uc.complete_manifest("code", state)
