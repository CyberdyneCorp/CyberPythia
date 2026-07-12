"""Unit tests for API key use cases (spec: auth, rest-api)."""

from datetime import UTC, datetime

from app.application.use_cases.api_keys import ApiKeyUseCases
from app.domain.services.api_key_factory import API_KEY_PREFIX, hash_api_key
from tests.unit.interfaces.conftest import FakeApiKeyPort


async def test_create_returns_plaintext_and_stores_only_hash():
    port = FakeApiKeyPort()
    created = await ApiKeyUseCases(port).create(
        label="claude-agent", created_by="admin-1", expires_in_days=30
    )
    assert created.plaintext.startswith(API_KEY_PREFIX)
    stored = next(iter(port.keys.values()))
    # persisted record holds the hash, never the plaintext
    assert stored.key_hash == hash_api_key(created.plaintext)
    assert created.plaintext not in (stored.key_hash, stored.prefix)
    assert stored.label == "claude-agent"
    assert stored.created_by == "admin-1"
    assert stored.expires_at is not None
    assert stored.expires_at > datetime.now(UTC)


async def test_create_without_expiry_is_non_expiring():
    port = FakeApiKeyPort()
    created = await ApiKeyUseCases(port).create(label="perm", created_by="admin-1")
    assert created.key.expires_at is None


async def test_create_defaults_to_unrestricted_org_scope():
    port = FakeApiKeyPort()
    created = await ApiKeyUseCases(port).create(label="a", created_by="admin-1")
    # None = unrestricted, preserving pre-#64 behavior for keys created without a list.
    assert created.key.allowed_organizations is None


async def test_create_normalises_org_scope_lowercased_and_deduped():
    port = FakeApiKeyPort()
    created = await ApiKeyUseCases(port).create(
        label="a", created_by="admin-1", allowed_organizations=["CyberDyne", "cyberdyne", "Amini"]
    )
    assert created.key.allowed_organizations == ["amini", "cyberdyne"]


async def test_create_empty_org_list_is_stored_as_unrestricted():
    # An empty selection is normalised to NULL (unrestricted) rather than a
    # deny-all key that could never authenticate.
    port = FakeApiKeyPort()
    created = await ApiKeyUseCases(port).create(
        label="a", created_by="admin-1", allowed_organizations=[]
    )
    assert created.key.allowed_organizations is None


async def test_list_returns_all_keys():
    port = FakeApiKeyPort()
    uc = ApiKeyUseCases(port)
    await uc.create(label="a", created_by="admin-1")
    await uc.create(label="b", created_by="admin-1")
    assert {k.label for k in await uc.list()} == {"a", "b"}


async def test_revoke_marks_key_revoked():
    port = FakeApiKeyPort()
    uc = ApiKeyUseCases(port)
    created = await uc.create(label="a", created_by="admin-1")
    assert await uc.revoke(created.key.id) is True
    assert next(iter(port.keys.values())).revoked is True


async def test_revoke_unknown_returns_false():
    from uuid import uuid4

    assert await ApiKeyUseCases(FakeApiKeyPort()).revoke(uuid4()) is False


async def test_delete_removes_key():
    port = FakeApiKeyPort()
    uc = ApiKeyUseCases(port)
    created = await uc.create(label="a", created_by="admin-1")
    assert await uc.delete(created.key.id) is True
    assert port.keys == {}


async def test_delete_unknown_returns_false():
    from uuid import uuid4

    assert await ApiKeyUseCases(FakeApiKeyPort()).delete(uuid4()) is False
