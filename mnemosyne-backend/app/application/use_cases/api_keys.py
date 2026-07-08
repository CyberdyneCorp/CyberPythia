"""API key management use cases (spec: auth, rest-api).

Creation returns the plaintext key exactly once; only its hash is persisted.
Keys grant read/query access and are managed by administrators.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.domain.entities.api_key import ApiKey
from app.domain.ports.persistence_ports import ApiKeyPort
from app.domain.services.api_key_factory import (
    display_prefix,
    generate_api_key,
    hash_api_key,
)


@dataclass(slots=True)
class CreatedApiKey:
    """A freshly issued key: metadata plus the one-time plaintext secret."""

    key: ApiKey
    plaintext: str


class ApiKeyUseCases:
    def __init__(self, api_keys: ApiKeyPort) -> None:
        self._api_keys = api_keys

    async def create(
        self, *, label: str, created_by: str, expires_in_days: int | None = None
    ) -> CreatedApiKey:
        now = datetime.now(UTC)
        expires_at = (
            now + timedelta(days=expires_in_days) if expires_in_days else None
        )
        plaintext = generate_api_key()
        key = ApiKey(
            id=uuid4(),
            label=label,
            prefix=display_prefix(plaintext),
            key_hash=hash_api_key(plaintext),
            created_by=created_by,
            created_at=now,
            expires_at=expires_at,
            revoked=False,
        )
        await self._api_keys.save(key)
        return CreatedApiKey(key=key, plaintext=plaintext)

    async def list(self) -> list[ApiKey]:
        return await self._api_keys.list_all()

    async def revoke(self, key_id: UUID) -> bool:
        return await self._api_keys.revoke(key_id)
