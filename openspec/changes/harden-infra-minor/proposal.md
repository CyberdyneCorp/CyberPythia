# Harden infra defaults, pin images/actions, and minor code hardening

## Why

Wave-4 review surfaced a cluster of low-severity infrastructure and code-hardening
findings. None is individually critical, but together they widen the attack
surface of dev/deploy defaults and leak more than necessary:

- **#61 (MEDIUM, CWE-732).** `docker-compose.yml` publishes the dev datastores
  (Postgres, Redis, MinIO) on `0.0.0.0` with weak/no auth — Redis has no password
  at all. On a shared or laptop-on-untrusted-network setup they are reachable
  off-host.
- **#72 (LOW, CWE-1104).** Both compose files pin MinIO to the mutable
  `minio/minio:latest` tag, so a rebuild can silently pull a different image.
- **#73 (LOW, CWE-200).** The unauthenticated `/api/v1/health` probe returns
  per-component up/down plus the failing exception **class names**, disclosing
  internal topology to any anonymous caller.
- **#74 (LOW, CWE-829).** CI actions are pinned to mutable tags
  (`actions/checkout@v4`, `astral-sh/setup-uv@v5`, `actions/setup-node@v4`).
- **#82 (INFO, CWE-89-like).** The agent-memory free-text search interpolates the
  caller's `query` into a `LIKE` pattern without escaping `%`/`_`, so those
  characters act as wildcards.
- **#83 (INFO, CWE-22).** `full_name`/`path` are f-string-interpolated into
  GitHub REST URLs and MinIO object keys without encoding or traversal checks.
- **#84 (INFO, CWE-327).** The degraded-mode fallback feature-hash uses
  `hashlib.md5`.
- **#85 (INFO).** Redis/MinIO/worker/mcp/web lack healthchecks; dependents start
  on `service_started`, so they can come up before their datastores are ready.

## What changes

- **#61.** Bind every published dev-datastore port to `127.0.0.1`, and give Redis
  a `--requirepass` password sourced from `.env` (`REDIS_PASSWORD`). `REDIS_URL`
  (compose services + `.env.example`) carries the password so local dev keeps
  working.
- **#72.** Pin MinIO to a released tag **and digest** in both compose files.
- **#73.** Split health: the public `/api/v1/health` returns only
  `{"status": "ok"|"degraded"}` at HTTP 200 (preserving the container/rollout
  healthcheck contract), and a new admin-gated `GET /api/v1/admin/health` returns
  the per-component `checks` map. No per-dependency detail or exception class
  name is exposed anonymously.
- **#74.** Pin each CI action to the full commit SHA of the current release for
  its major, with a `# vX.Y.Z` comment.
- **#82.** Escape `LIKE` metacharacters (`\`, `%`, `_`) and cap the query length
  before binding, using `ilike(..., escape="\\")`, so the query matches literally.
- **#83.** URL-encode each path segment (`quote(seg, safe="")`, preserving `/`)
  before interpolating `full_name`/`path`/`branch` into request URLs, and reject
  object-storage keys containing `..` traversal segments.
- **#84.** Replace `md5` with `blake2b` for the fallback bucketing (same modulo
  scheme). Only affects the OpenAI-unavailable degraded-mode fallback vector, so
  there is no production embedding impact.
- **#85.** Add healthchecks to Redis/MinIO/worker/mcp/web (and the api HTTP probe)
  in both compose files and gate dependents on `service_healthy`.

## Impact

- Affected specs: `rest-api` (public health minimised, admin health added),
  `agent-memory` (literal free-text search), `repository-sync` (safe raw-snapshot
  object keys).
- Affected code: `app/interfaces/api/routers/health.py`, `app/main.py`,
  `app/infrastructure/persistence/repositories/misc.py`,
  `app/infrastructure/github/client.py`,
  `app/infrastructure/vector/pgvector_store.py`.
- Affected config (no spec impact): `docker-compose.yml`, `compose.coolify.yaml`,
  `.env.example`, `.github/workflows/ci.yml`.
- Security: closes off-host datastore exposure (#61), image drift (#72, #74),
  health information disclosure (#73), LIKE-wildcard injection (#82), URL/object-key
  traversal (#83), and weak-hash use (#84). No behavior change for normal inputs.

### Verification (config-only items)

- `docker compose config` and `docker compose -f compose.coolify.yaml config`
  resolve with the new port bindings, MinIO digest pins, Redis password, and
  healthchecks.
- CI validates the action SHA pins: a wrong SHA fails the workflow checkout.
