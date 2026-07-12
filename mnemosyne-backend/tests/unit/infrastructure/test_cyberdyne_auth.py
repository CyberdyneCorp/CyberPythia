"""Unit tests for CyberdyneAuth verification adapters (HTTP mocked with respx)."""

import time

import httpx
import jwt
import pytest
import respx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.config import Settings
from app.domain.ports.auth_port import AuthUnavailableError, TokenInvalidError
from app.infrastructure.auth.cyberdyne_auth import (
    CyberdyneAuthAdapter,
    IntrospectionVerifier,
    JwksVerifier,
)

ISSUER = "https://auth.test"
KID = "test-key-1"


@pytest.fixture(scope="module")
def rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="module")
def jwks(rsa_key):
    public_numbers = rsa_key.public_key().public_numbers()

    def b64uint(n: int) -> str:
        import base64

        data = n.to_bytes((n.bit_length() + 7) // 8, "big")
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    return {
        "keys": [
            {
                "kty": "RSA",
                "kid": KID,
                "use": "sig",
                "alg": "RS256",
                "n": b64uint(public_numbers.n),
                "e": b64uint(public_numbers.e),
            }
        ]
    }


@pytest.fixture
def settings():
    return Settings(
        cyberdyneauth_issuer=ISSUER,
        cyberdyneauth_token_issuer=ISSUER,
        cyberdyneauth_client_id="mnemosyne-backend",
        cyberdyneauth_client_secret="secret",
        _env_file=None,
    )


def make_token(rsa_key, *, kid=KID, exp_offset=600, **claims) -> str:
    payload = {"iss": ISSUER, "sub": "user-1", "exp": int(time.time()) + exp_offset, **claims}
    pem = rsa_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return jwt.encode(payload, pem, algorithm="RS256", headers={"kid": kid})


@respx.mock
async def test_jwks_valid_token(settings, rsa_key, jwks):
    respx.get(f"{ISSUER}/.well-known/jwks.json").respond(json=jwks)
    token = make_token(
        rsa_key,
        scope="mnemosyne:admin openid",
        is_admin=False,
        entitlements=["mnemosyne"],
        username="satoshi",
    )
    identity = await JwksVerifier(settings).verify(token)
    assert identity.subject == "user-1"
    assert identity.username == "satoshi"
    assert identity.can_access("mnemosyne")
    assert identity.can_administer("mnemosyne:admin")


@respx.mock
async def test_jwks_expired_token_rejected(settings, rsa_key, jwks):
    respx.get(f"{ISSUER}/.well-known/jwks.json").respond(json=jwks)
    token = make_token(rsa_key, exp_offset=-10)
    with pytest.raises(TokenInvalidError):
        await JwksVerifier(settings).verify(token)


@respx.mock
async def test_jwks_wrong_issuer_rejected(settings, rsa_key, jwks):
    respx.get(f"{ISSUER}/.well-known/jwks.json").respond(json=jwks)
    token = jwt.encode(
        {"iss": "https://evil.test", "sub": "u", "exp": int(time.time()) + 600},
        rsa_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
        algorithm="RS256",
        headers={"kid": KID},
    )
    with pytest.raises(TokenInvalidError):
        await JwksVerifier(settings).verify(token)


@respx.mock
async def test_jwks_unknown_kid_refetches_then_rejects(settings, rsa_key, jwks):
    route = respx.get(f"{ISSUER}/.well-known/jwks.json").respond(json=jwks)
    token = make_token(rsa_key, kid="other-kid")
    with pytest.raises(TokenInvalidError, match="unknown signing key"):
        await JwksVerifier(settings).verify(token)
    assert route.call_count >= 1


@respx.mock
async def test_jwks_unknown_kid_refetch_throttled_by_cooldown(settings, rsa_key, jwks):
    # CWE-770: a caller streaming random unknown kids must not amplify one JWKS
    # GET per request. Within the min-refresh window at most ONE refetch happens.
    settings = settings.model_copy(update={"auth_jwks_min_refresh_seconds": 3600})
    route = respx.get(f"{ISSUER}/.well-known/jwks.json").respond(json=jwks)
    verifier = JwksVerifier(settings)
    for _ in range(25):
        token = make_token(rsa_key, kid=f"attacker-{time.monotonic_ns()}")
        with pytest.raises(TokenInvalidError, match="unknown signing key"):
            await verifier.verify(token)
    assert route.call_count == 1  # only the first unknown kid triggered a fetch


@respx.mock
async def test_jwks_ttl_expiry_still_refreshes(settings, rsa_key, jwks):
    # The cooldown must not defeat the normal TTL-based refresh.
    settings = settings.model_copy(
        update={"auth_jwks_cache_ttl_seconds": 0, "auth_jwks_min_refresh_seconds": 3600}
    )
    route = respx.get(f"{ISSUER}/.well-known/jwks.json").respond(json=jwks)
    verifier = JwksVerifier(settings)
    await verifier.verify(make_token(rsa_key, entitlements=["mnemosyne"]))
    await verifier.verify(make_token(rsa_key, entitlements=["mnemosyne"]))
    assert route.call_count == 2  # TTL=0 -> refetch every call despite cooldown


@respx.mock
async def test_jwks_wrong_audience_rejected(settings, rsa_key, jwks):
    # CWE-287: a token carrying an `aud` that isn't ours must be rejected.
    respx.get(f"{ISSUER}/.well-known/jwks.json").respond(json=jwks)
    token = make_token(rsa_key, entitlements=["mnemosyne"], aud="some-other-service")
    with pytest.raises(TokenInvalidError):
        await JwksVerifier(settings).verify(token)


@respx.mock
async def test_jwks_correct_audience_accepted(settings, rsa_key, jwks):
    respx.get(f"{ISSUER}/.well-known/jwks.json").respond(json=jwks)
    token = make_token(rsa_key, entitlements=["mnemosyne"], aud="mnemosyne")
    identity = await JwksVerifier(settings).verify(token)
    assert identity.subject == "user-1"


@respx.mock
async def test_jwks_no_audience_still_accepted(settings, rsa_key, jwks):
    # User tokens legitimately carry no `aud` — they must keep working.
    respx.get(f"{ISSUER}/.well-known/jwks.json").respond(json=jwks)
    token = make_token(rsa_key, entitlements=["mnemosyne"])
    identity = await JwksVerifier(settings).verify(token)
    assert identity.subject == "user-1"


@respx.mock
async def test_force_introspection_rejects_revoked_admin_token(settings, rsa_key, jwks):
    # CWE-613: a locally-valid JWT that embeds entitlements must still be rejected
    # on a sensitive path when introspection reports it revoked (active: false).
    respx.get(f"{ISSUER}/.well-known/jwks.json").respond(json=jwks)
    respx.post(f"{ISSUER}/api/v1/auth/oauth2/token").respond(
        json={"access_token": "svc-token", "expires_in": 900}
    )
    respx.post(f"{ISSUER}/api/v1/auth/introspect").respond(json={"active": False})
    token = make_token(rsa_key, entitlements=["mnemosyne"], is_admin=True)
    adapter = CyberdyneAuthAdapter(settings=settings)
    # Normal path trusts the embedded entitlements and succeeds...
    assert (await adapter.verify(token)).is_admin
    # ...but forcing introspection catches the revocation.
    with pytest.raises(TokenInvalidError):
        await adapter.verify(token, force_introspection=True)


@respx.mock
async def test_jwks_unreachable_raises_unavailable(settings, rsa_key):
    respx.get(f"{ISSUER}/.well-known/jwks.json").mock(side_effect=httpx.ConnectError("down"))
    with pytest.raises(AuthUnavailableError):
        await JwksVerifier(settings).verify(make_token(rsa_key))


async def test_malformed_token_rejected(settings):
    with pytest.raises(TokenInvalidError):
        await JwksVerifier(settings).verify("not-a-jwt")


@respx.mock
async def test_introspection_active_token(settings):
    respx.post(f"{ISSUER}/api/v1/auth/oauth2/token").respond(
        json={"access_token": "svc-token", "expires_in": 900, "token_type": "Bearer"}
    )
    # Contract mirror of CyberdyneAuth IntrospectionResponse schema
    respx.post(f"{ISSUER}/api/v1/auth/introspect").respond(
        json={
            "active": True,
            "sub": "agent-1",
            "client_id": "agent-client",
            "username": None,
            "scope": "openid",
            "entitlements": ["mnemosyne"],
            "is_admin": False,
            "token_type": "access_token",
            "aud": None,
            "exp": int(time.time()) + 600,
            "iat": int(time.time()),
        }
    )
    identity = await IntrospectionVerifier(settings).verify("opaque-or-jwt")
    assert identity.subject == "agent-1"
    assert identity.client_id == "agent-client"
    assert identity.can_access("mnemosyne")


@respx.mock
async def test_introspection_inactive_token_rejected(settings):
    respx.post(f"{ISSUER}/api/v1/auth/oauth2/token").respond(
        json={"access_token": "svc-token", "expires_in": 900}
    )
    respx.post(f"{ISSUER}/api/v1/auth/introspect").respond(json={"active": False})
    with pytest.raises(TokenInvalidError, match="not active"):
        await IntrospectionVerifier(settings).verify("revoked")


@respx.mock
async def test_introspection_service_token_cached(settings):
    token_route = respx.post(f"{ISSUER}/api/v1/auth/oauth2/token").respond(
        json={"access_token": "svc-token", "expires_in": 900}
    )
    respx.post(f"{ISSUER}/api/v1/auth/introspect").respond(
        json={"active": True, "sub": "u", "entitlements": []}
    )
    verifier = IntrospectionVerifier(settings)
    await verifier.verify("t1")
    await verifier.verify("t2")
    assert token_route.call_count == 1  # cached between calls


@respx.mock
async def test_introspection_retries_once_on_401(settings):
    respx.post(f"{ISSUER}/api/v1/auth/oauth2/token").respond(
        json={"access_token": "svc-token", "expires_in": 900}
    )
    introspect_route = respx.post(f"{ISSUER}/api/v1/auth/introspect")
    introspect_route.side_effect = [
        httpx.Response(401),
        httpx.Response(200, json={"active": True, "sub": "u", "entitlements": ["mnemosyne"]}),
    ]
    identity = await IntrospectionVerifier(settings).verify("t")
    assert identity.subject == "u"
    assert introspect_route.call_count == 2


@respx.mock
async def test_adapter_jwks_mode_falls_back_when_no_entitlements_claim(
    settings, rsa_key, jwks
):
    respx.get(f"{ISSUER}/.well-known/jwks.json").respond(json=jwks)
    respx.post(f"{ISSUER}/api/v1/auth/oauth2/token").respond(
        json={"access_token": "svc-token", "expires_in": 900}
    )
    respx.post(f"{ISSUER}/api/v1/auth/introspect").respond(
        json={"active": True, "sub": "user-1", "entitlements": ["mnemosyne"], "is_admin": False}
    )
    token = make_token(rsa_key)  # no entitlements claim in the JWT
    identity = await CyberdyneAuthAdapter(settings=settings).verify(token)
    assert identity.can_access("mnemosyne")  # came from introspection


@respx.mock
async def test_adapter_jwks_mode_uses_local_claims_when_present(settings, rsa_key, jwks):
    respx.get(f"{ISSUER}/.well-known/jwks.json").respond(json=jwks)
    token = make_token(rsa_key, entitlements=["mnemosyne"])
    identity = await CyberdyneAuthAdapter(settings=settings).verify(token)
    assert identity.can_access("mnemosyne")  # no introspection route mocked -> local path used


@respx.mock
async def test_adapter_introspect_mode_always_introspects(settings, rsa_key):
    settings_introspect = settings.model_copy(update={"auth_validation_mode": "introspect"})
    respx.post(f"{ISSUER}/api/v1/auth/oauth2/token").respond(
        json={"access_token": "svc-token", "expires_in": 900}
    )
    respx.post(f"{ISSUER}/api/v1/auth/introspect").respond(json={"active": False})
    token = make_token(rsa_key, entitlements=["mnemosyne"])  # locally valid
    with pytest.raises(TokenInvalidError):
        await CyberdyneAuthAdapter(settings=settings_introspect).verify(token)
