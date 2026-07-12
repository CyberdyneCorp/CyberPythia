# DoS resilience for the REST API

## Why

The REST API has no defenses against resource-exhaustion abuse (CWE-770):

- **No rate limiting** anywhere — `app/main.py` wires only CORS and error
  handlers. A single caller can hammer the cost-bearing LLM/embedding routes
  (`/ask`, `/context-pack`, `/feature-document`, `/search`, `/code-search`,
  `/intelligence/search`) or the unauthenticated webhook/health endpoints and
  drive unbounded compute, third-party spend, or downtime.
- **Unbounded webhook body** — the GitHub webhook receiver reads the full body
  and `json.loads` it *before* the HMAC/size check, with no cap, so an
  unauthenticated caller can post an arbitrarily large payload.
- **Unbounded `limit` params** — several intelligence and repository endpoints
  accept a user `limit` that flows straight into a SQL `LIMIT`, letting a caller
  request an unbounded result set.

## What changes

- Add request **rate limiting** (slowapi) keyed by the caller's credential when
  present, else client IP. Three buckets, all configurable via settings:
  a sane global default on every route, a stricter bucket on the cost-bearing
  LLM/embedding routes, and a bucket on the unauthenticated webhook + health
  endpoints. Exceeding a limit returns **429** with a `Retry-After` header in the
  standard error envelope. Rate limiting is toggleable (off in tests).
- Enforce a configurable **webhook body-size cap** (default 1 MiB): reject with
  **413** based on `Content-Length` before reading the body, and on the actual
  byte length after reading, both *before* JSON parsing and HMAC verification.
- **Bound every user `limit` query param** with `ge=1, le=MAX_PAGE_SIZE`, reusing
  the existing pagination bound, so oversized values are rejected with **422**.

## Impact

- `app/config.py`: `rate_limit_enabled`, `rate_limit_default`, `rate_limit_llm`,
  `rate_limit_webhook`, `rate_limit_health`, `webhook_max_body_bytes`.
- New `app/interfaces/api/rate_limit.py` (Limiter, key func, 429 handler).
- `app/main.py`: register the limiter, its exception handler, and middleware.
- `app/interfaces/api/routers/{repositories,intelligence,health,webhooks}.py`:
  strict-bucket decorators, bounded `limit` params, webhook body cap.
- New dependency: `slowapi`.
- rest-api spec: rate-limiting, webhook body-cap, and bounded-limit requirements.
