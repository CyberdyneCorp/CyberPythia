# Harden secrets, webhook-secret handling, and SSRF-adjacent URL validation

## Why

Wave-3 backend review surfaced eight low/informational hardening gaps around
secret handling and outbound URL trust:

- **Empty webhook secret is verifiable (#67, CWE-347).** The receiver guards the
  installation secret with `is not None`, so a connection whose stored webhook
  secret is the empty string is treated as valid. HMAC-SHA256 under a known-empty
  key is forgeable, letting anyone submit a "signed" delivery. Nothing stops an
  empty secret from being persisted in the first place.
- **Encryption key reused for state signing + no boot check (#68, CWE-320).** The
  signed-CSRF `state` HMAC reuses the Fernet `TOKEN_ENCRYPTION_KEY` directly (no
  key separation), and an empty/invalid key is only detected lazily on first
  credential use rather than at boot.
- **Committed datastore credentials (#69, CWE-798).** `docker-compose.yml` inlines
  working `POSTGRES_PASSWORD` / `MINIO_ROOT_PASSWORD` values.
- **Known-value config defaults (#70, CWE-1188).** `database_url` and
  `minio_secret_key` default to working local credentials, so a misconfigured
  production deploy silently runs on them.
- **SSRF via GitHub pagination (#71, CWE-918).** The client follows the upstream
  `Link: rel=next` URL and re-attaches the bearer token, so a hostile upstream
  could redirect the authenticated request to an internal or foreign host.
- **Unvalidated alert webhook (#78, CWE-918).** `alert_webhook_url` is POSTed to
  without host validation (SSRF to internal services / cloud metadata).
- **Unvalidated GitHub API base (#79, CWE-918).** `github_api_base_url` is used
  with the bearer token but never checked; an internal override is an SSRF sink.
- **Open redirect via App html_url (#80, CWE-601).** After manifest conversion the
  app redirects to `{creds.html_url}/installations/new` using a GitHub-supplied,
  attacker-influenceable value without verifying it is GitHub-hosted.

## What changes

- **Reject empty webhook secrets (#67).** An empty/blank stored secret resolves to
  "no secret" (`webhook_secret_for_installation` returns `None`) so the receiver
  401s instead of verifying under a known-empty key. Persisting a connection —
  manual App-connect or manifest onboarding — with a blank webhook secret is
  refused.
- **Secret key separation + boot validation (#68/#70/#79).** The signed-state HMAC
  key is derived from `TOKEN_ENCRYPTION_KEY` via HKDF-SHA256 with a fixed info
  label (independent from the Fernet key). Settings gain `validate_runtime()`,
  called at container build, which fails fast when `app_env=production` and any of
  `TOKEN_ENCRYPTION_KEY` / `DATABASE_URL` / `MINIO_SECRET_KEY` is unset, and which
  rejects an internal/non-https `github_api_base_url` outside dev/test. The
  sensitive settings now default to empty (no committed working credential); dev
  and test tolerate empty/default secrets and internal API overrides.
- **One SSRF host guard reused across sinks (#71/#78/#79).** A new
  `app/infrastructure/security/url_guard.py` rejects non-https URLs and hosts that
  are — or resolve to — loopback / link-local / RFC1918 / otherwise non-public
  addresses, with an opt-in dev localhost exception. It backs: the GitHub
  pagination follow decision (same-origin https only), the alert-webhook
  construction check, and the API-base boot check.
- **Committed credentials removed (#69).** `docker-compose.yml` references
  `${POSTGRES_PASSWORD}` / `${MINIO_ROOT_PASSWORD}` (and users) resolved from an
  untracked `.env`; `.env.example` documents them so `docker compose config`
  resolves.
- **Install-redirect origin check (#80).** Manifest completion verifies
  `creds.html_url` is same-origin with the configured `github_web_base_url` before
  using it as the install redirect; otherwise it raises and the router falls back
  to the dashboard error redirect.

## Impact

- Affected specs: `webhooks` (empty-secret delivery rejected), `github-connection`
  (empty webhook secret refused on persistence; install redirect must be
  GitHub-hosted), and a new `platform-hardening` capability (fail-fast secret
  configuration, signed-state key separation, SSRF-safe outbound URLs).
- Affected code: `app/config.py`, `app/composition.py`,
  `app/application/use_cases/github_connections.py`,
  `app/infrastructure/security/token_encryption.py`,
  `app/infrastructure/security/url_guard.py` (new),
  `app/infrastructure/github/client.py`,
  `app/infrastructure/notify/webhook_notifier.py`, `docker-compose.yml`,
  `.env.example`, and `tests/conftest.py` (supplies dev secret values now that the
  defaults are empty).
- Security: closes #67, #68, #69, #70, #71, #78, #79, #80. No behavior change for
  correctly configured dev/test or production deployments; production now fails
  fast on missing secrets or an internal API base instead of running silently.
