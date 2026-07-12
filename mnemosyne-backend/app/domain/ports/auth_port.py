"""Inbound-auth port: verify a bearer token into a CallerIdentity (design D1/D2)."""

from typing import Protocol

from app.domain.value_objects.identity import CallerIdentity


class TokenInvalidError(Exception):
    """Signature/issuer/expiry check failed, or token revoked."""


class AuthUnavailableError(Exception):
    """The auth plane (JWKS/introspection) cannot be reached."""


class AuthPort(Protocol):
    async def verify(self, token: str, *, force_introspection: bool = False) -> CallerIdentity:
        """Return the caller identity or raise TokenInvalidError/AuthUnavailableError.

        ``force_introspection`` forces the authoritative, revocation-aware path for
        sensitive (admin) operations, regardless of any entitlements the token
        embeds locally (spec: auth, CWE-613).
        """
        ...
