# Tasks

- [x] 1. Add DoS-resilience settings to `app/config.py` (rate-limit buckets + webhook body cap)
- [x] 2. Add `slowapi` dependency
- [x] 3. New `app/interfaces/api/rate_limit.py`: Limiter keyed by credential/IP, callable limits, 429 + Retry-After handler
- [x] 4. Wire limiter + exception handler + `SlowAPIMiddleware` in `app/main.py`; toggle enabled from settings
- [x] 5. Apply strict-bucket decorators to cost-bearing routes (`/ask`, `/context-pack`, `/feature-document`, repo `/search`, `/code-search`, `/intelligence/search`) and unauth routes (`/webhooks/github`, `/health`)
- [x] 6. Enforce webhook body-size cap (413) before parse/HMAC in `webhooks.py`
- [x] 7. Bound every user `limit` query param with `ge=1, le=MAX_PAGE_SIZE` in `intelligence.py` and `repositories.py`
- [x] 8. Disable rate limiting by default in the test settings fixture
- [x] 9. Regression tests: oversized `limit` → 422, oversized webhook body → 413 before signature, rate-limit exceeded → 429 + Retry-After
- [x] 10. ruff, mypy, unit + persistence-integration suites green
