# Tasks

## #67 — Reject empty webhook secrets
- [x] 1. `webhook_secret_for_installation` decrypts the stored secret and returns
      `None` when it is empty/blank (delivery 401s instead of verifying)
- [x] 2. `connect_app` and `complete_manifest` refuse to persist a blank webhook
      secret
- [x] 3. Tests: blank stored secret → lookup `None`; connect/manifest reject blank

## #68 / #70 / #79 — Secret key separation + fail-fast boot validation
- [x] 4. `derive_signed_state_secret` (HKDF-SHA256) yields a distinct state HMAC
      key; composition derives it instead of reusing the Fernet key
- [x] 5. `Settings.validate_runtime()` fails fast in production on empty
      `TOKEN_ENCRYPTION_KEY` / `DATABASE_URL` / `MINIO_SECRET_KEY`, and rejects an
      internal/non-https `github_api_base_url` outside dev/test; called at
      container build
- [x] 6. `database_url` / `minio_secret_key` default to empty (no committed
      credential); `tests/conftest.py` supplies parseable dev values
- [x] 7. Tests: prod+empty → error; dev/test tolerate empties; internal API base
      rejected in prod/staging, allowed in dev; state key ≠ Fernet key; signed
      state round-trips under the derived secret

## #71 / #78 — SSRF host guard
- [x] 8. Add `app/infrastructure/security/url_guard.py` (public-https guard +
      same-origin follow check) reused across sinks
- [x] 9. GitHub client only follows a same-origin https `next` link (token not
      sent off-allowlist)
- [x] 10. `WebhookNotifier` validates its URL at construction (dev localhost
      exception)
- [x] 11. Tests: off-host/internal `next` link not followed; IMDS/internal alert
      URL rejected

## #69 — Remove committed datastore credentials
- [x] 12. `docker-compose.yml` uses `${POSTGRES_PASSWORD}` / `${MINIO_ROOT_PASSWORD}`;
      `.env.example` documents them; `docker compose config` resolves

## #80 — Install-redirect origin check
- [x] 13. `complete_manifest` verifies `creds.html_url` is same-origin with
      `github_web_base_url` before redirecting; else raises → dashboard error
- [x] 14. Test: an off-site `html_url` is rejected (not used as the redirect)
