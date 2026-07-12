"""#68 (CWE-320): signed-state HMAC key is derived (HKDF) from — and distinct
from — the Fernet token-encryption key, giving cryptographic key separation."""

from datetime import UTC, datetime, timedelta

from app.domain.services.signed_state import sign_state, verify_state
from app.infrastructure.security.token_encryption import derive_signed_state_secret

FERNET_KEY = "3sJ6l1n5x3Qw2p8vY0aZ9bC4dE7fG1hI2jK3lM4nO5="


def test_state_secret_differs_from_encryption_key():
    derived = derive_signed_state_secret(FERNET_KEY)
    assert derived != FERNET_KEY
    assert len(derived) == 64  # 32 bytes hex


def test_derivation_is_deterministic():
    assert derive_signed_state_secret(FERNET_KEY) == derive_signed_state_secret(FERNET_KEY)


def test_distinct_keys_derive_distinct_secrets():
    assert derive_signed_state_secret("key-a") != derive_signed_state_secret("key-b")


def test_signed_state_round_trips_under_derived_secret():
    secret = derive_signed_state_secret(FERNET_KEY)
    token = sign_state(
        secret,
        organization="cyberdyne",
        subject="admin-1",
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )
    payload = verify_state(secret, token)
    assert payload["org"] == "cyberdyne"
    assert payload["sub"] == "admin-1"


def test_empty_key_still_derives_usable_secret():
    # Dev/test run with an empty token-encryption key; derivation must not raise.
    secret = derive_signed_state_secret("")
    assert secret and secret != ""
