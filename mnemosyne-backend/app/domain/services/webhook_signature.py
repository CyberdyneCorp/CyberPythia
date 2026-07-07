"""GitHub webhook HMAC-SHA256 signature verification (spec: webhooks; design D3)."""

import hashlib
import hmac


def compute_signature(secret: str, body: bytes) -> str:
    """The `sha256=<hex>` value GitHub sends in X-Hub-Signature-256."""
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify_signature(secret: str, body: bytes, signature_header: str | None) -> bool:
    """Constant-time compare of the delivered signature against the computed one."""
    if not signature_header:
        return False
    expected = compute_signature(secret, body)
    return hmac.compare_digest(expected, signature_header)
