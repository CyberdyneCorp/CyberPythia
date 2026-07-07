# Proposal: add-sync-observability-endpoints

## Why

The nightly scheduled job now discovers, auto-enables, and syncs ~238 repositories, with staggered
enqueues and fail-fast rate-limit handling. But an admin has **no way to watch it**: the per-run
summary (enqueued / skipped / failed, discovered / newly-enabled) is only logged and thrown away,
and there is no endpoint to see which individual repos failed — or whether a failure was a
rate-limit skip vs. a real error. To trust and tune the nightly run (especially the first few on a
personal PAT), we need to surface both.

Per-repo sync jobs are already persisted with status, per-step errors (a rate-limit failure lands
in the failed step's error text), timestamps, and trigger — they just aren't listable across repos.
The scheduled-run summary is not persisted at all.

## What Changes

- **Persist scheduled-run outcomes**: a `sync_run_history` table + `SyncRun` entity. The daily cron
  records one row per run: timestamps, trigger, the discovery counters (discovered, newly_enabled,
  skipped_archived), and the sync counters (enqueued, skipped, failed).
- **List recent per-repo sync jobs**: `SyncJobPort.list_recent(limit)` + adapter, returning recent
  jobs across all repositories with status, trigger, timestamps, and failed-step errors.
- **Admin endpoints** (existing admin auth):
  - `GET /api/v1/admin/sync-runs` — recent scheduled-run summaries (newest first).
  - `GET /api/v1/admin/sync-jobs` — recent sync jobs with repository name, status, trigger, times,
    and any failed-step error messages (so rate-limit skips are visible).

### Non-goals (future changes)

- A per-run id linking individual sync jobs to the scheduled run that enqueued them (jobs are
  correlated by time window + `triggered_by=scheduler`, which is sufficient here).
- A live-updating dashboard / websocket feed (these are simple polled admin reads).
- Retention/pruning of run history (rows are tiny; add later if needed).
- Structured rate-limit metrics/alerting (the failed-step error text carries the reason for now).

## Capabilities

### Modified Capabilities (additive deltas)

- `repository-sync`: ADDED — record each scheduled run's outcome summary.
- `rest-api`: ADDED — admin endpoints to list recent scheduled-run summaries and recent sync jobs.

## Impact

- **Data model**: one new table `sync_run_history` (small, append-only). One Alembic migration `0005`.
- **Code**: `SyncRun` entity, `SyncRunPort` + Postgres adapter, `SyncJobPort.list_recent`, cron
  records a run, two admin endpoints + response schemas. Reuses the existing admin-auth dependency.
- **Dependencies**: none new.
- **Security**: read-only admin endpoints behind the existing `AdminCaller`; they expose sync
  metadata (repo names, statuses, error strings) — no repository content or credentials.
- **Load**: recording one row per nightly run; the listings are bounded (limit, newest-first).
