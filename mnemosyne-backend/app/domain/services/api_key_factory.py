"""API key generation and hashing (spec: auth).

Keys look like ``mnem_<43 url-safe chars>``. Only the SHA-256 hash is persisted;
the display prefix is the first few non-secret characters shown in the UI.
"""

import hashlib
import secrets

API_KEY_PREFIX = "mnem_"
_DISPLAY_PREFIX_LEN = len(API_KEY_PREFIX) + 8


def generate_api_key() -> str:
    """A fresh, high-entropy plaintext key. Shown once, never stored."""
    return f"{API_KEY_PREFIX}{secrets.token_urlsafe(32)}"


def hash_api_key(key: str) -> str:
    """Stable SHA-256 hex used for constant-lookup and at-rest storage."""
    return hashlib.sha256(key.encode()).hexdigest()


def display_prefix(key: str) -> str:
    """Non-secret prefix (e.g. ``mnem_ab12cd34``) for identifying a key in lists."""
    return key[:_DISPLAY_PREFIX_LEN]
