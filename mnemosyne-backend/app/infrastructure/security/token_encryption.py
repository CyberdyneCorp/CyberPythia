"""Symmetric encryption for GitHub credentials at rest (spec: github-connection)."""

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.config import get_settings


class TokenEncryptionError(Exception):
    pass


def derive_signed_state_secret(token_encryption_key: str) -> str:
    """Derive a distinct HMAC key for signed CSRF state from the encryption key.

    Reusing the Fernet token-encryption key directly to sign `signed_state`
    couples two unrelated secrets (#68, CWE-320). HKDF-SHA256 with a fixed info
    label yields an independent key from the same root, so a weakness or exposure
    in one signing context can't be leveraged against the other. Works with an
    empty key in dev/test (deterministic derivation, no configured secret needed).
    """
    derived = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b"mnemosyne/signed-state/v1",
    ).derive(token_encryption_key.encode())
    return derived.hex()


class TokenEncryption:
    def __init__(self, key: str | None = None) -> None:
        key = key or get_settings().token_encryption_key
        if not key:
            raise TokenEncryptionError("TOKEN_ENCRYPTION_KEY is not configured")
        try:
            self._fernet = Fernet(key.encode())
        except ValueError as exc:
            raise TokenEncryptionError("TOKEN_ENCRYPTION_KEY is not a valid Fernet key") from exc

    def encrypt(self, plaintext: str) -> bytes:
        return self._fernet.encrypt(plaintext.encode())

    def decrypt(self, ciphertext: bytes) -> str:
        try:
            return self._fernet.decrypt(ciphertext).decode()
        except InvalidToken as exc:
            raise TokenEncryptionError("credential cannot be decrypted with this key") from exc
