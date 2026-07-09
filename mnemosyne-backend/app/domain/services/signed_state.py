"""Signed, stateless CSRF state for the GitHub App manifest round-trip (spec: auth).

A compact token binding the initiating admin + organization + expiry, HMAC-signed so
the GitHub redirect callbacks can be verified without server-side session storage
(works across instances). Not secret — integrity + expiry only.
"""

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Any


class InvalidStateError(Exception):
    """State token missing, malformed, tampered, or expired."""


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def sign_state(secret: str, *, organization: str, subject: str, expires_at: datetime) -> str:
    payload = {"org": organization, "sub": subject, "exp": int(expires_at.timestamp())}
    body = _b64e(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    sig = _b64e(hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def verify_state(secret: str, token: str, *, now: datetime | None = None) -> dict[str, Any]:
    """Return the payload (org, sub, exp) or raise InvalidState."""
    now = now or datetime.now(UTC)
    try:
        body, sig = token.split(".", 1)
    except (ValueError, AttributeError) as exc:
        raise InvalidStateError("malformed state") from exc
    expected = _b64e(hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expected):
        raise InvalidStateError("bad signature")
    try:
        payload: dict[str, Any] = json.loads(_b64d(body))
    except (ValueError, json.JSONDecodeError) as exc:
        raise InvalidStateError("undecodable state") from exc
    if int(payload.get("exp", 0)) < int(now.timestamp()):
        raise InvalidStateError("expired state")
    return payload
