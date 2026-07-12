"""Request rate limiting (spec: rest-api; CWE-770).

A single module-level :class:`slowapi.Limiter` is shared by every route so the
decorators below can be applied at import time. It is keyed by the caller's
*authenticated* identity when auth has run (so authenticated callers get a
per-identity budget) and falls back to the real client IP for unauthenticated
traffic. A raw ``Authorization`` header is never trusted as the key.

Three buckets:
  * a sane global default applied to all routes (via ``SlowAPIMiddleware``);
  * a stricter bucket for cost-bearing LLM/embedding routes;
  * a bucket for the unauthenticated webhook + health endpoints.

All limits are read from :class:`app.config.Settings` on every request, so
tests can tighten or disable them without re-importing this module.
"""

import time

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import get_settings
from app.interfaces.api.errors import error_body

# Request-state attribute the auth dependency sets to the verified caller's
# subject once a token is validated. Read here so the limiter keys authenticated
# traffic by proven identity rather than any client-supplied header.
RL_SUBJECT_ATTR = "rl_caller_subject"


def _client_ip(request: Request) -> str:
    """Real client IP, honouring ``X-Forwarded-For`` behind trusted proxies.

    With ``rate_limit_trusted_proxy_hops`` (N) proxies in front of the app, the
    true client is the Nth ``X-Forwarded-For`` entry from the right; entries to
    its left are client-supplied and untrusted. With 0 hops the header is
    ignored and the peer address is used, so a directly internet-facing deploy
    can't be spoofed. Requires uvicorn ``--proxy-headers`` so ``request.client``
    also reflects the forwarded peer (see docs/deploy-coolify.md); otherwise all
    forwarded traffic collapses onto the single proxy IP.
    """
    hops = get_settings().rate_limit_trusted_proxy_hops
    if hops > 0:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            parts = [p.strip() for p in forwarded.split(",") if p.strip()]
            if parts:
                # Fewer entries than trusted hops: fall back to the left-most
                # (earliest) entry, the closest thing to the true client we have.
                return parts[-hops] if len(parts) >= hops else parts[0]
    return get_remote_address(request)


def caller_key(request: Request) -> str:
    """Identify the caller for rate limiting.

    Keys by the authenticated caller's subject once auth has verified the token
    (each credential gets its own budget); unauthenticated requests — including
    ``/webhooks/github`` and ``/health`` — are keyed by the real client IP. The
    raw ``Authorization`` header is deliberately never used as the key: trusting
    an unverified header would let an attacker supply arbitrary values to mint
    unlimited fresh buckets and escape the limit on those exact endpoints.
    """
    subject: str | None = getattr(request.state, RL_SUBJECT_ATTR, None)
    if subject:
        return "auth:" + subject
    return _client_ip(request)


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
