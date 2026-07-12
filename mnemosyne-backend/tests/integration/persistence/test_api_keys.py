"""Integration tests for PostgresApiKeyRepository (real Postgres)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.domain.entities.api_key import ApiKey
from app.domain.services.api_key_factory import generate_api_key, hash_api_key
from app.infrastructure.persistence.repositories.misc import PostgresApiKeyRepository

NOW = datetime(2026, 7, 8, 12, 0, tzinfo=UTC)

pytestmark = pytest.mark.integration


def _key(
    plaintext, *, label="agent", expires_at=None, revoked=False, created_at=NOW,
    allowed_organizations=None,
) -> ApiKey:
    return ApiKey(
        id=uuid4(), label=label, prefix=plaintext[:13], key_hash=hash_api_key(plaintext),
        created_by="admin-1", created_at=created_at, expires_at=expires_at, revoked=revoked,
        allowed_organizations=allowed_organizations,
    )


class TestApiKeyRoundTrip:
    async def test_save_and_lookup_by_hash(self, session_factory):
        adapter = PostgresApiKeyRepository(session_factory)
        plaintext = generate_api_key()
        await adapter.save(_key(plaintext, expires_at=NOW + timedelta(days=30)))
        found = await adapter.get_by_hash(hash_api_key(plaintext))
        assert found is not None
        assert found.label == "agent"
        assert found.expires_at is not None
        assert found.is_valid(NOW)

    async def test_lookup_miss_returns_none(self, session_factory):
        adapter = PostgresApiKeyRepository(session_factory)
        assert await adapter.get_by_hash(hash_api_key("mnem_nope")) is None

    async def test_org_scope_column_round_trips(self, session_factory):
        # #64: the nullable allowed_organizations column persists a list; a key
        # stored without it reads back as None (unrestricted).
        adapter = PostgresApiKeyRepository(session_factory)
        scoped_pt, open_pt = generate_api_key(), generate_api_key()
        await adapter.save(_key(scoped_pt, allowed_organizations=["cyberdyne", "aminitech"]))
        await adapter.save(_key(open_pt, allowed_organizations=None))
        scoped = await adapter.get_by_hash(hash_api_key(scoped_pt))
        unscoped = await adapter.get_by_hash(hash_api_key(open_pt))
        assert scoped is not None and scoped.allowed_organizations == ["cyberdyne", "aminitech"]
        assert unscoped is not None and unscoped.allowed_organizations is None

    async def test_list_newest_first(self, session_factory):
        adapter = PostgresApiKeyRepository(session_factory)
        await adapter.save(_key(generate_api_key(), label="old", created_at=NOW - timedelta(days=1)))
        await adapter.save(_key(generate_api_key(), label="new", created_at=NOW))
        labels = [k.label for k in await adapter.list_all()]
        assert labels.index("new") < labels.index("old")

    async def test_revoke(self, session_factory):
        adapter = PostgresApiKeyRepository(session_factory)
        plaintext = generate_api_key()
        key = _key(plaintext)
        await adapter.save(key)
        assert await adapter.revoke(key.id) is True
        found = await adapter.get_by_hash(hash_api_key(plaintext))
        assert found is not None and found.revoked is True
        assert not found.is_valid(NOW)

    async def test_revoke_unknown_returns_false(self, session_factory):
        adapter = PostgresApiKeyRepository(session_factory)
        assert await adapter.revoke(uuid4()) is False

    async def test_delete_removes_row(self, session_factory):
        adapter = PostgresApiKeyRepository(session_factory)
        plaintext = generate_api_key()
        key = _key(plaintext)
        await adapter.save(key)
        assert await adapter.delete(key.id) is True
        assert await adapter.get_by_hash(hash_api_key(plaintext)) is None

    async def test_delete_unknown_returns_false(self, session_factory):
        adapter = PostgresApiKeyRepository(session_factory)
        assert await adapter.delete(uuid4()) is False
