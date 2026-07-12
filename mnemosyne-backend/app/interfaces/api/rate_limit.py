"""Request rate limiting (spec: rest-api; CWE-770).

A single module-level :class:`slowapi.Limiter` is shared by every route so the
decorators below can be applied at import time. It is keyed by the caller's
credential when present (so authenticated callers get a per-identity budget)
and falls back to the client IP for unauthenticated traffic.

Three buckets:
  * a sane global default applied to all routes (via ``SlowAPIMiddleware``);
  * a stricter bucket for cost-bearing LLM/embedding routes;
  * a bucket for the unauthenticated webhook + health endpoints.

All limits are read from :class:`app.config.Settings` on every request, so
tests can tighten or disable them without re-importing this module.
"""

import hashlib
import time

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import get_settings
from app.interfaces.api.errors import error_body


def caller_key(request: Request) -> str:
    """Identify the caller for rate limiting.

    The ``Authorization`` header carries both bearer JWTs and Mnemosyne API
    keys, so hashing it yields a stable per-caller identity without decoding
    the credential. Unauthenticated requests fall back to the client IP.
    """
    auth = request.headers.get("Authorization")
    if auth:
        return "auth:" + hashlib.sha256(auth.encode("utf-8")).hexdigest()
    return get_remote_address(request)


def _default_limit() -> str:
    return get_settings().rate_limit_default


def llm_limit() -> str:
    return get_settings().rate_limit_llm


def webhook_limit() -> str:
    return get_settings().rate_limit_webhook


def health_limit() -> str:
    return get_settings().rate_limit_health


# headers_enabled stays False: slowapi's success-path header injection requires
# every decorated endpoint to return (or declare) a Response, which our JSON
# endpoints don't. The 429 handler sets Retry-After itself instead.
limiter = Limiter(key_func=caller_key, default_limits=[_default_limit])


def _retry_after_seconds(request: Request) -> int:
    """Seconds until the exceeded window resets (>= 1)."""
    try:
        item, args = request.state.view_rate_limit
        reset_at, _ = limiter.limiter.get_window_stats(item, *args)
        return max(1, int(1 + reset_at - time.time()))
    except Exception:
        return 60


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """429 in the app's error envelope, with a Retry-After header."""
    response = JSONResponse(
        status_code=429,
        content=error_body("rate_limited", f"rate limit exceeded: {exc.detail}"),
        headers={"Retry-After": str(_retry_after_seconds(request))},
    )
    return response
