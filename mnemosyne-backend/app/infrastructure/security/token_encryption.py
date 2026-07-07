"""Symmetric encryption for GitHub credentials at rest (spec: github-connection)."""

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


class TokenEncryptionError(Exception):
    pass


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
