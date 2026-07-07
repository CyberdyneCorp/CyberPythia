"""CyberdyneAuth token verification adapters (design D1).

Two verification paths:

- ``JwksVerifier`` — local RS256 validation against the published JWKS.
  Fast path; no per-request call to the auth plane.
- ``IntrospectionVerifier`` — RFC 7662 ``POST /api/v1/auth/introspect``,
  authenticated with Mnemosyne's own client-credentials service token.
  Authoritative (revocation-aware) and the source of ``entitlements``.

``CyberdyneAuthAdapter`` composes them per ``AUTH_VALIDATION_MODE``:
``jwks`` validates locally and falls back to introspection when the JWT
carries no entitlements claim; ``introspect`` always introspects.
"""

import time
from typing import Any

import httpx
import jwt
from jwt import PyJWK

from app.config import Settings, get_settings
from app.domain.ports.auth_port import AuthUnavailableError, TokenInvalidError
from app.domain.value_objects.identity import CallerIdentity


def _identity_from_claims(claims: dict[str, Any]) -> CallerIdentity:
    scope = claims.get("scope") or ""
    entitlements = claims.get("entitlements") or []
    if isinstance(entitlements, str):
        entitlements = entitlements.split()
    return CallerIdentity(
        subject=str(claims.get("sub", "")),
        username=claims.get("username") or claims.get("email"),
        client_id=claims.get("client_id"),
        scopes=frozenset(scope.split()) if scope else frozenset(),
        entitlements=frozenset(str(e) for e in entitlements),
        is_admin=bool(claims.get("is_admin", False)),
    )


class JwksVerifier:
    """Verifies RS256 JWTs against the CyberdyneAuth JWKS with a TTL cache."""

    def __init__(self, settings: Settings | None = None, client: httpx.AsyncClient | None = None):
        self._settings = settings or get_settings()
        self._client = client
        self._keys: dict[str, PyJWK] = {}
        self._fetched_at: float = 0.0

    async def _fetch_jwks(self) -> None:
        client = self._client or httpx.AsyncClient()
        try:
            response = await client.get(self._settings.jwks_url, timeout=10)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AuthUnavailableError(f"JWKS fetch failed: {exc}") from exc
        finally:
            if self._client is None:
                await client.aclose()
        self._keys = {
            key["kid"]: PyJWK(key)
            for key in response.json().get("keys", [])
            if key.get("kid")
        }
        self._fetched_at = time.monotonic()

    async def _get_key(self, kid: str) -> PyJWK:
        expired = time.monotonic() - self._fetched_at > self._settings.auth_jwks_cache_ttl_seconds
        if kid not in self._keys or expired:
            await self._fetch_jwks()  # refresh on unknown kid or TTL expiry (spec: auth)
        key = self._keys.get(kid)
        if key is None:
            raise TokenInvalidError("unknown signing key")
        return key

    async def verify(self, token: str) -> CallerIdentity:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.InvalidTokenError as exc:
            raise TokenInvalidError("malformed token") from exc
        kid = header.get("kid")
        if not kid:
            raise TokenInvalidError("token has no kid")
        key = await self._get_key(kid)
        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                issuer=self._settings.cyberdyneauth_issuer,
                options={"require": ["exp", "sub"], "verify_aud": False},
            )
        except jwt.InvalidTokenError as exc:
            # Single opaque error: never reveal which check failed (spec: auth)
            raise TokenInvalidError("token validation failed") from exc
        return _identity_from_claims(claims)

    def claims_have_entitlements(self, token: str) -> bool:
        """Whether the (already verified) token embeds an entitlements claim."""
        claims = jwt.decode(token, options={"verify_signature": False})
        return "entitlements" in claims


class IntrospectionVerifier:
    """RFC 7662 introspection, authenticated with our own service token."""

    def __init__(self, settings: Settings | None = None, client: httpx.AsyncClient | None = None):
        self._settings = settings or get_settings()
        self._client = client
        self._service_token: str | None = None
        self._service_token_expiry: float = 0.0

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        client = self._client or httpx.AsyncClient()
        try:
            return await client.request(method, url, timeout=10, **kwargs)
        except httpx.HTTPError as exc:
            raise AuthUnavailableError(f"auth plane unreachable: {exc}") from exc
        finally:
            if self._client is None:
                await client.aclose()

    async def _get_service_token(self) -> str:
        if self._service_token and time.monotonic() < self._service_token_expiry:
            return self._service_token
        response = await self._request(
            "POST",
            self._settings.token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self._settings.cyberdyneauth_client_id,
                "client_secret": self._settings.cyberdyneauth_client_secret,
            },
        )
        if response.status_code != 200:
            raise AuthUnavailableError(
                f"service token acquisition failed: {response.status_code}"
            )
        payload = response.json()
        self._service_token = payload["access_token"]
        # refresh 60s before expiry
        self._service_token_expiry = time.monotonic() + payload.get("expires_in", 900) - 60
        return self._service_token

    async def verify(self, token: str) -> CallerIdentity:
        service_token = await self._get_service_token()
        response = await self._request(
            "POST",
            self._settings.introspection_url,
            data={"token": token},
            headers={"Authorization": f"Bearer {service_token}"},
        )
        if response.status_code == 401:
            # our service token was rejected — refresh once and retry
            self._service_token = None
            service_token = await self._get_service_token()
            response = await self._request(
                "POST",
                self._settings.introspection_url,
                data={"token": token},
                headers={"Authorization": f"Bearer {service_token}"},
            )
        if response.status_code != 200:
            raise AuthUnavailableError(f"introspection failed: {response.status_code}")
        payload = response.json()
        if not payload.get("active", False):
            raise TokenInvalidError("token is not active")
        return _identity_from_claims(payload)


class CyberdyneAuthAdapter:
    """AuthPort implementation honoring AUTH_VALIDATION_MODE (design D1)."""

    def __init__(
        self,
        jwks: JwksVerifier | None = None,
        introspection: IntrospectionVerifier | None = None,
        settings: Settings | None = None,
    ):
        self._settings = settings or get_settings()
        self._jwks = jwks or JwksVerifier(self._settings)
        self._introspection = introspection or IntrospectionVerifier(self._settings)

    async def verify(self, token: str) -> CallerIdentity:
        if self._settings.auth_validation_mode == "introspect":
            return await self._introspection.verify(token)
        identity = await self._jwks.verify(token)
        if not identity.entitlements and not self._jwks.claims_have_entitlements(token):
            # JWT lacks entitlements; introspection is the authoritative source (design D1)
            return await self._introspection.verify(token)
        return identity
