# Deploying Mnemosyne on Coolify

Follows the house conventions from cyberdynedao `docs/deploy-coolify.md` and
CyberdyneAuth `compose.coolify.yaml`.

## 1. Create the resource

Coolify → New Resource → **Docker Compose** → this repository, compose file
`compose.coolify.yaml`.

## 2. Environment variables

| Variable | Value | Secret |
| --- | --- | --- |
| `POSTGRES_PASSWORD` | strong random | 🔒 |
| `MINIO_ROOT_PASSWORD` | strong random | 🔒 |
| `TOKEN_ENCRYPTION_KEY` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` | 🔒 |
| `CYBERDYNEAUTH_ISSUER` | `https://auth.backend.coolify.cyberdynecorp.ai` | |
| `CYBERDYNEAUTH_CLIENT_ID` | backend service client id | |
| `CYBERDYNEAUTH_CLIENT_SECRET` | its secret | 🔒 |
| `OPENAI_API_KEY` | embeddings + ask (optional → degraded mode) | 🔒 |
| `PUBLIC_API_BASE_URL` | `https://mnemosyne.backend.<domain>` | |
| `PUBLIC_AUTH_CLIENT_ID` | `mnemosyne-web` | |
| `SCHEDULED_SYNC_ENABLED` | `true` (default) — daily full re-sync of all enabled repos | |
| `SCHEDULED_SYNC_HOUR` | UTC hour for the daily sync (default `3`) | |
| `SCHEDULED_SYNC_MINUTE` | minute of that hour (default `0`) | |
| `SCHEDULED_DISCOVERY_ENABLED` | `true` (default) — daily re-discovery before the sync | |
| `AUTO_ENABLE_NEW_REPOS` | `true` (default) — auto-enable newly-seen non-archived repos | |
| `AUTO_ENABLE_MODE` | indexing mode for auto-enabled repos (default `project_intelligence`) | |
| `AUTO_ENABLE_ARCHIVED` | `false` (default) — skip archived repos when auto-enabling | |
| `DEFAULT_ORG_SYNC_ENABLED` | `true` (default) — a newly-discovered org syncs unless toggled off | |
| `SCHEDULED_SYNC_STAGGER_SECONDS` | defer between successive nightly enqueues (default `5.0`) | |
| `GITHUB_RATE_LIMIT_MAX_WAIT_SECONDS` | cap on in-request rate-limit wait; beyond it, fail fast (default `60`) | |

## Scheduled daily sync

The `mnemosyne-worker` runs an `arq` cron once per day (default **03:00 UTC**) that enqueues a
full sync for every **enabled** repository, so metrics, health, delivery analytics, and the
metrics time-series refresh at least daily even without webhooks. It reuses the normal sync
pipeline: a repo already syncing is skipped, the daily fan-out is absorbed by the worker's
`max_jobs` limit and per-repo locks, and one repo failing does not stop the rest. Set
`SCHEDULED_SYNC_ENABLED=false` to turn it off, or change the hour/minute. It logs
`scheduled full sync: enqueued=… skipped=… failed=…` on each run.

Before the sync, the same daily job re-runs **discovery** for every connection and
**auto-enables newly-appearing non-archived repositories** in `AUTO_ENABLE_MODE` (default
`project_intelligence` — docs/OpenSpec/issues/PRs/metrics, no source embeddings, cheap at
scale). It only enables repos whose GitHub id was **not seen before**, so a repository an admin
has manually **disabled is never re-enabled**. Turn it off with `AUTO_ENABLE_NEW_REPOS=false`
(or `SCHEDULED_DISCOVERY_ENABLED=false` to skip discovery entirely). Enabling the *existing*
already-discovered repos is a separate one-time admin action (bulk `PATCH /api/v1/repos/{id}`
with `{"enabled": true, "indexing_mode": "project_intelligence"}`).

**Watching the runs.** Two admin-only endpoints surface sync activity:
`GET /api/v1/admin/sync-runs` lists each nightly run's summary (discovered / newly-enabled /
enqueued / skipped / failed, with timestamps), and `GET /api/v1/admin/sync-jobs` lists recent
per-repository sync jobs with status, trigger, times, and any failed-step error text — so a
rate-limited or otherwise failed repo, and its reason, is visible.

**Rate-limit resilience.** The nightly fan-out **staggers** its enqueues
(`SCHEDULED_SYNC_STAGGER_SECONDS`, default 5s apart) to smooth the request rate, and the GitHub
client **bounds** how long a single call waits on a rate limit: it honours `Retry-After` and
`X-RateLimit-Reset` up to `GITHUB_RATE_LIMIT_MAX_WAIT_SECONDS` (default 60s), then **fails that
call fast** so the worker slot is freed and the repo is retried on the next daily run — rather
than blocking a slot for up to an hour. On a large enabled set this trades one repo's freshness
for completing the overall run; the durable capacity fix is an org fine-grained PAT or GitHub App
(higher hourly limits).

## 3. Domains

| Service | Port | Domain |
| --- | --- | --- |
| `mnemosyne-api` | 8000 | `mnemosyne.backend.<domain>` |
| `mnemosyne-mcp` | 8100 | `mnemosyne.mcp.<domain>` — set the domain **with the port** (`https://mnemosyne.mcp.<domain>:8100`) so Coolify routes to container port 8100 instead of the image's first exposed port |
| `mnemosyne-web` | 3000 | `mnemosyne.<domain>` |

If the MCP domain differs from the default, also set
`FASTMCP_HTTP_ALLOWED_HOSTS='["mnemosyne.mcp.<domain>"]'` — FastMCP's
DNS-rebinding protection returns 421 for Host headers not on the allowlist.

The API container runs `alembic upgrade head` on boot.

### One-click MCP OAuth (optional, off by default)

To let `claude.ai` / Claude Desktop connect with no hand-pasted token, enable the
`mnemosyne-mcp` OAuth proxy (bridges to CyberdyneAuth, which lacks DCR):

1. Provision a CyberdyneAuth confidential client `mnemosyne-mcp` —
   `grant_types: [authorization_code, refresh_token]`,
   `allowed_audiences: ["mnemosyne"]`, redirect URI
   `https://mnemosyne.mcp.<domain>/auth/callback`.
2. Set on `mnemosyne-mcp`: `MCP_OAUTH_ENABLED=true`,
   `MCP_OAUTH_PUBLIC_BASE_URL=https://mnemosyne.mcp.<domain>`,
   `MCP_OAUTH_CLIENT_ID`, `MCP_OAUTH_CLIENT_SECRET` (🔒).

When enabled the server serves `/.well-known/oauth-authorization-server`,
`/.well-known/oauth-protected-resource/mcp`, `/register` (DCR), `/authorize`,
`/token`, and `/auth/callback`. API-key (`mnem_…`) and direct-bearer auth keep
working unchanged. The logged-in user must hold the `mnemosyne` entitlement.

## 4. Rollout order (design: Migration Plan)

1. Deploy; wait until `GET /api/v1/health` returns `"status": "ok"`.
2. Register the OAuth clients + `mnemosyne` entitlement in CyberdyneAuth
   ([auth-integration.md](auth-integration.md)); update the web client's
   `redirect_uris` with the production callback URL.
3. Sign in to the dashboard as an admin, register the read-only GitHub PAT,
   run discovery, enable pilot repositories, trigger the first syncs.
4. Run the staging BDD suite:

   ```bash
   STAGING_AUTH_ISSUER=https://auth.backend.coolify.cyberdynecorp.ai \
   STAGING_AUTH_CLIENT_ID=<bdd-client> \
   STAGING_AUTH_CLIENT_SECRET=<secret> \
   STAGING_MCP_URL=https://mnemosyne-mcp.<domain> \
   just test-bdd-staging   # STAGING_SERVER_URL=https://mnemosyne.backend.<domain>
   ```

Rollback: services are stateless — redeploy the previous image. Database
rollback via `alembic downgrade` (pre-GA only).
