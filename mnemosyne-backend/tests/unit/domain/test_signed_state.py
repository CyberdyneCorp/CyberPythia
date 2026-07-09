"""Unit tests for the signed CSRF state (spec: auth / github-connection)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.domain.services.signed_state import (
    InvalidStateError,
    sign_state,
    verify_state,
)

SECRET = "test-hmac-secret"


def _future() -> datetime:
    return datetime.now(UTC) + timedelta(minutes=30)


def test_round_trip():
    token = sign_state(SECRET, organization="CyberdyneCorp", subject="admin-1", expires_at=_future())
    payload = verify_state(SECRET, token)
    assert payload["org"] == "CyberdyneCorp"
    assert payload["sub"] == "admin-1"


def test_tampered_signature_rejected():
    token = sign_state(SECRET, organization="Org", subject="s", expires_at=_future())
    body, _sig = token.split(".", 1)
    with pytest.raises(InvalidStateError):
        verify_state(SECRET, f"{body}.deadbeef")


def test_wrong_secret_rejected():
    token = sign_state(SECRET, organization="Org", subject="s", expires_at=_future())
    with pytest.raises(InvalidStateError):
        verify_state("other-secret", token)


def test_expired_rejected():
    token = sign_state(
        SECRET, organization="Org", subject="s",
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    with pytest.raises(InvalidStateError):
        verify_state(SECRET, token)


def test_malformed_rejected():
    with pytest.raises(InvalidStateError):
        verify_state(SECRET, "not-a-token")
