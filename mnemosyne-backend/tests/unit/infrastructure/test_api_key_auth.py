"""Unit tests for the API-key aware auth adapter (spec: auth)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.domain.entities.api_key import ApiKey
from app.domain.ports.auth_port import TokenInvalidError
from app.domain.services.api_key_factory import (
    generate_api_key,
    hash_api_key,
)
from app.domain.value_objects.identity import CallerIdentity
from app.infrastructure.auth.api_key_auth import ApiKeyAuthAdapter
from tests.unit.interfaces.conftest import FakeApiKeyPort

NOW = datetime(2026, 7, 8, tzinfo=UTC)


class FakeFallback:
    def __init__(self):
        self.calls = []

    async def verify(self, token, *, force_introspection=False):
        self.calls.append(token)
        return CallerIdentity(subject="cyberdyne-user", entitlements=frozenset({"mnemosyne"}))


def _adapter(port, fallback, entitlement="mnemosyne"):
    return ApiKeyAuthAdapter(
        api_keys=port, fallback=fallback, entitlement=entitlement, now=lambda: NOW
    )


async def _store(port, plaintext, *, expires_at=None, revoked=False, allowed_organizations=None):
    key = ApiKey(
        id=uuid4(), label="agent", prefix=plaintext[:13], key_hash=hash_api_key(plaintext),
        created_by="admin-1", created_at=NOW - timedelta(days=1),
        expires_at=expires_at, revoked=revoked, allowed_organizations=allowed_organizations,
    )
    await port.save(key)
    return key


async def test_valid_key_grants_entitled_non_admin_caller():
    port, fallback = FakeApiKeyPort(), FakeFallback()
    plaintext = generate_api_key()
    key = await _store(port, plaintext, expires_at=NOW + timedelta(days=30))
    caller = await _adapter(port, fallback).verify(plaintext)
    assert caller.can_access("mnemosyne")
    assert caller.is_admin is False
    # CWE-269: API keys are read/query only — never allowed to mutate.
    assert caller.is_read_only is True
    assert caller.subject == f"apikey:{key.id}"
    assert not fallback.calls  # never delegated


async def test_bearer_fallback_caller_is_not_read_only():
    port, fallback = FakeApiKeyPort(), FakeFallback()
    caller = await _adapter(port, fallback).verify("eyJ.a.cyberdyne.jwt")
    assert caller.is_read_only is False


async def test_non_expiring_key_valid():
    port, fallback = FakeApiKeyPort(), FakeFallback()
    plaintext = generate_api_key()
    await _store(port, plaintext, expires_at=None)
    caller = await _adapter(port, fallback).verify(plaintext)
    assert caller.can_access("mnemosyne")


async def test_unknown_key_rejected():
    port, fallback = FakeApiKeyPort(), FakeFallback()
    with pytest.raises(TokenInvalidError):
        await _adapter(port, fallback).verify(generate_api_key())
    assert not fallback.calls


async def test_expired_key_rejected():
    port, fallback = FakeApiKeyPort(), FakeFallback()
    plaintext = generate_api_key()
    await _store(port, plaintext, expires_at=NOW - timedelta(seconds=1))
    with pytest.raises(TokenInvalidError):
        await _adapter(port, fallback).verify(plaintext)


async def test_revoked_key_rejected():
    port, fallback = FakeApiKeyPort(), FakeFallback()
    plaintext = generate_api_key()
    await _store(port, plaintext, expires_at=NOW + timedelta(days=30), revoked=True)
    with pytest.raises(TokenInvalidError):
        await _adapter(port, fallback).verify(plaintext)


async def test_non_api_key_bearer_delegates_to_fallback():
    port, fallback = FakeApiKeyPort(), FakeFallback()
    caller = await _adapter(port, fallback).verify("eyJ.a.cyberdyne.jwt")
    assert caller.subject == "cyberdyne-user"
    assert fallback.calls == ["eyJ.a.cyberdyne.jwt"]


async def test_entitlement_matches_configured_product_key():
    # In production REQUIRED_ENTITLEMENT is the product client_id, not "mnemosyne".
    port, fallback = FakeApiKeyPort(), FakeFallback()
    plaintext = generate_api_key()
    await _store(port, plaintext, expires_at=None)
    caller = await _adapter(port, fallback, entitlement="cyb_50UdgxXphi9SJJQX").verify(plaintext)
    assert caller.can_access("cyb_50UdgxXphi9SJJQX")
    assert not caller.can_access("mnemosyne")  # only the configured key is granted


class TestOrgScopedKeys:
    """#64: an API key may be restricted to specific organizations, reusing the
    same org-scope mechanism as user tokens (no parallel authz path)."""

    async def test_unscoped_key_is_unrestricted(self):
        port, fallback = FakeApiKeyPort(), FakeFallback()
        plaintext = generate_api_key()
        await _store(port, plaintext, allowed_organizations=None)
        caller = await _adapter(port, fallback).verify(plaintext)
        assert caller.can_access("mnemosyne")
        # None = unrestricted: reaches every org (backward compatible).
        assert caller.allowed_organizations("mnemosyne") is None

    async def test_scoped_key_restricts_to_its_orgs(self):
        port, fallback = FakeApiKeyPort(), FakeFallback()
        plaintext = generate_api_key()
        await _store(port, plaintext, allowed_organizations=["CyberDyne", "aminitech"])
        caller = await _adapter(port, fallback).verify(plaintext)
        # Still entitled to authenticate + read.
        assert caller.can_access("mnemosyne")
        # ...but bounded to exactly its (lower-cased) orgs.
        assert caller.allowed_organizations("mnemosyne") == frozenset(
            {"cyberdyne", "aminitech"}
        )

    async def test_scoped_key_denied_cross_org_via_contextvar(self):
        from app.domain.services.org_scope import (
            is_organization_allowed,
            set_allowed_organizations,
        )

        port, fallback = FakeApiKeyPort(), FakeFallback()
        plaintext = generate_api_key()
        await _store(port, plaintext, allowed_organizations=["cyberdyne"])
        caller = await _adapter(port, fallback).verify(plaintext)

        # Applying the caller's boundary (as the security layer does) denies other
        # orgs at the repository-store choke point while allowing its own.
        set_allowed_organizations(caller.allowed_organizations("mnemosyne"))
        assert is_organization_allowed("cyberdyne") is True
        assert is_organization_allowed("victim-org") is False
