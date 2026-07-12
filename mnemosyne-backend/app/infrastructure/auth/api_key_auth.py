"""API-key aware auth adapter (spec: auth).

Wraps the CyberdyneAuth adapter. A bearer beginning with the ``mnem_`` prefix is
resolved against Mnemosyne's own API keys; anything else falls through to the
wrapped CyberdyneAuth validation unchanged. A valid key yields an entitled,
**non-admin** caller (read/query access only).
"""

from collections.abc import Callable
from datetime import UTC, datetime

from app.domain.ports.auth_port import AuthPort, TokenInvalidError
from app.domain.ports.persistence_ports import ApiKeyPort
from app.domain.services.api_key_factory import API_KEY_PREFIX, hash_api_key
from app.domain.value_objects.identity import CallerIdentity


class ApiKeyAuthAdapter:
    """Composite AuthPort: API keys first, then CyberdyneAuth."""

    def __init__(
        self,
        *,
        api_keys: ApiKeyPort,
        fallback: AuthPort,
        entitlement: str,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._api_keys = api_keys
        self._fallback = fallback
        self._entitlement = entitlement
        self._now = now or (lambda: datetime.now(UTC))

    async def verify(self, token: str, *, force_introspection: bool = False) -> CallerIdentity:
        if token.startswith(API_KEY_PREFIX):
            key = await self._api_keys.get_by_hash(hash_api_key(token))
            if key is None or not key.is_valid(self._now()):
                raise TokenInvalidError("invalid or expired API key")
            # API keys are read/query only: never admin, never mutating (CWE-269).
            return CallerIdentity(
                subject=f"apikey:{key.id}",
                username=key.label,
                client_id=f"apikey:{key.id}",
                entitlements=self._entitlements_for(key.allowed_organizations),
                is_admin=False,
                is_read_only=True,
            )
        return await self._fallback.verify(token, force_introspection=force_introspection)

    def _entitlements_for(self, allowed_organizations: list[str] | None) -> frozenset[str]:
        """Encode the key's org boundary through the SAME entitlement mechanism as
        user tokens, so the downstream org-scope contextvar is populated identically
        and there is no parallel authz path (#64, spec: auth).

        - ``None`` / empty  -> the bare entitlement: unrestricted (all orgs).
        - ``[org, ...]``     -> plan-qualified entitlements ``entitlement:<org>`` that
          ``CallerIdentity.allowed_organizations`` resolves to exactly those orgs.
        """
        if not allowed_organizations:
            return frozenset({self._entitlement})
        return frozenset(
            f"{self._entitlement}:{org.lower()}" for org in allowed_organizations
        )
