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
    audience = claims.get("aud") or []
    if isinstance(audience, str):
        audience = [audience]
    return CallerIdentity(
        subject=str(claims.get("sub", "")),
        username=claims.get("username") or claims.get("email"),
        client_id=claims.get("client_id"),
        scopes=frozenset(scope.split()) if scope else frozenset(),
        entitlements=frozenset(str(e) for e in entitlements),
        audiences=frozenset(str(a) for a in audience),
        is_admin=bool(claims.get("is_admin", False)),
        authorized_org_logins=_org_logins_from_claims(claims),
    )


def _org_logins_from_claims(claims: dict[str, Any]) -> frozenset[str] | None:
    """Parse the CyberdyneAuth ``orgs`` claim into GitHub org logins (lower-cased).

    Returns ``None`` when the claim is absent (legacy token) so the caller falls
    back to the legacy entitlement derivation; a present claim yields the set of
    non-null ``github_login`` values (possibly empty). Orgs not yet mapped to a
    GitHub login (``github_login`` null) are omitted — they simply won't match,
    which is correct (CyberdyneAuth#104 / CyberPythia#77).
    """
    orgs = claims.get("orgs")
    if orgs is None:
        return None
    logins: set[str] = set()
    if isinstance(orgs, list):
        for entry in orgs:
            login = entry.get("github_login") if isinstance(entry, dict) else None
            if login:
                logins.add(str(login).lower())
    return frozenset(logins)


class JwksVerifier:
    """Verifies RS256 JWTs against the CyberdyneAuth JWKS with a TTL cache."""

    def __init__(self, settings: Settings | None = None, client: httpx.AsyncClient | None = None):
        self._settings = settings or get_settings()
        self._client = client
        self._keys: dict[str, PyJWK] = {}
        self._fetched_at: float = 0.0
        # Monotonic time of the last fetch *attempt* (success or failure). The
        # refetch throttle keys off this so a JWKS outage can't be amplified into
        # one outbound GET per request. Starts at -inf ("never attempted") so the
        # very first fetch is never throttled — otherwise, on a freshly-booted
        # host where time.monotonic() < cooldown, the cold-start fetch would be
        # wrongly suppressed and every token would fail to validate until the
        # window elapsed.
        self._attempted_at: float = float("-inf")

    async def _fetch_jwks(self) -> None:
        self._attempted_at = time.monotonic()
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
        now = time.monotonic()
        ttl_expired = now - self._fetched_at > self._settings.auth_jwks_cache_ttl_seconds
        stale = kid not in self._keys or ttl_expired
        # Refetch at most once per min-refresh window, measured from the last
        # attempt (success OR failure), so neither a caller streaming random kids
        # nor a JWKS outage (where the last success never advances) can amplify
        # into one outbound GET per request (CWE-770, spec: auth).
        throttle_open = now - self._attempted_at >= self._settings.auth_jwks_min_refresh_seconds
        if stale and throttle_open:
            await self._fetch_jwks()
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
                issuer=self._settings.cyberdyneauth_token_issuer,
                # `aud` is validated manually below: user tokens may legitimately
                # carry no audience, but a present `aud` MUST match (CWE-287).
                options={"require": ["exp", "sub"], "verify_aud": False},
            )
        except jwt.InvalidTokenError as exc:
            # Single opaque error: never reveal which check failed (spec: auth)
            raise TokenInvalidError("token validation failed") from exc
        self._check_audience(claims)
        return _identity_from_claims(claims)

    def _check_audience(self, claims: dict[str, Any]) -> None:
        """Reject a token that carries an `aud` claim not matching our audience.

        A missing/empty `aud` is allowed (user tokens); a present one must include
        the configured service audience (spec: auth, CWE-287).
        """
        aud = claims.get("aud")
        if not aud:
            return
        if isinstance(aud, str):
            audiences = [aud]
        elif isinstance(aud, (list, tuple)):
            audiences = [a for a in aud if isinstance(a, str)]
        else:
            # A malformed non-string/non-list `aud` fails closed (CWE-287) rather
            # than raising a TypeError that would surface as a 500.
            raise TokenInvalidError("token validation failed")
        if self._settings.service_audience not in audiences:
            raise TokenInvalidError("token validation failed")

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

    async def verify(self, token: str, *, force_introspection: bool = False) -> CallerIdentity:
        if force_introspection or self._settings.auth_validation_mode == "introspect":
            # Sensitive (admin) paths force the revocation-aware path regardless of
            # any entitlements embedded in the JWT (CWE-613, spec: auth).
            return await self._introspection.verify(token)
        identity = await self._jwks.verify(token)
        if not identity.entitlements and not self._jwks.claims_have_entitlements(token):
            # JWT lacks entitlements; introspection is the authoritative source (design D1)
            return await self._introspection.verify(token)
        return identity
