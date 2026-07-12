# Tasks

## #61 — Loopback-bound datastores + Redis auth (config)
- [x] 1. Bind published Postgres/Redis/MinIO ports to `127.0.0.1` in
      `docker-compose.yml`
- [x] 2. Add Redis `--requirepass ${REDIS_PASSWORD}`; thread the password through
      `REDIS_URL` in every compose service and `.env.example`
- [x] 3. Verify `docker compose config` resolves

## #72 — Pin MinIO image (config)
- [x] 4. Pin `minio/minio` to a released tag + digest in `docker-compose.yml` and
      `compose.coolify.yaml`

## #73 — Health information disclosure
- [x] 5. Public `/api/v1/health` returns only `{"status"}` at HTTP 200; add
      admin-gated `GET /api/v1/admin/health` returning the component `checks`
- [x] 6. Register the admin health router in `app/main.py`
- [x] 7. Tests: public health has no dependency/exception detail; admin health
      (authorized) has detail; unauthenticated → 401, non-admin → 403

## #74 — Pin CI actions (config)
- [x] 8. Pin `actions/checkout`, `astral-sh/setup-uv`, `actions/setup-node` to
      commit SHAs with `# vX.Y.Z` comments

## #82 — Literal free-text memory search
- [x] 9. Escape `\`/`%`/`_` and cap query length before `ilike(..., escape="\\")`
- [x] 10. Test: `%`/`_` are escaped literally and the query is length-capped

## #83 — Encode paths / safe object keys
- [x] 11. URL-encode `full_name`/`path`/`branch` segments before request URLs;
      reject `..` segments in raw-snapshot object keys
- [x] 12. Tests: special-char path is encoded; a traversing object key is rejected

## #84 — Non-md5 fallback hash
- [x] 13. Replace `md5` with `blake2b` for the fallback bucketing
- [x] 14. Test: bucketing is deterministic and differs from the md5 bucket

## #85 — Healthchecks + gated dependencies (config)
- [x] 15. Add healthchecks to Redis/MinIO/worker/mcp/web (+ api HTTP probe) in
      both compose files; gate dependents on `service_healthy`
- [x] 16. Verify both files with `docker compose config`
