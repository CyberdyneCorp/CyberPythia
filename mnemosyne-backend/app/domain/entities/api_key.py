"""Mnemosyne-issued API key entity (spec: auth).

A long-lived bearer credential Mnemosyne issues itself, accepted as an
alternative to a CyberdyneAuth token. Only the SHA-256 hash is persisted; the
plaintext is shown once at creation and never stored.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(slots=True)
class ApiKey:
    id: UUID
    label: str
    prefix: str  # non-secret display prefix, e.g. "mnem_ab12cd34"
    key_hash: str  # SHA-256 hex of the full plaintext key
    created_by: str  # subject of the admin who issued it
    created_at: datetime
    expires_at: datetime | None = None  # None = non-expiring
    revoked: bool = False
    # Organizations this key may access, lower-cased. ``None`` = unrestricted
    # (all orgs), preserving backward compatibility for keys issued before org
    # scoping existed. A non-empty list restricts the key to those orgs (#64).
    allowed_organizations: list[str] | None = None

    def is_valid(self, now: datetime) -> bool:
        """A key authenticates only while not revoked and not past expiry."""
        if self.revoked:
            return False
        return self.expires_at is None or self.expires_at > now
