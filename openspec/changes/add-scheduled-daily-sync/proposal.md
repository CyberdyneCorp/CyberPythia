# Proposal: add-scheduled-daily-sync

## Why

Today a repository is re-synced only when a webhook fires (which needs a GitHub App
installed — an ops step not yet done in production) or when an admin triggers a sync by
hand. There is **no scheduler**, so without webhooks the metrics, health scores, delivery
analytics, and the metrics time-series drift until someone manually re-syncs. The daily
snapshot that powers throughput/forecast trends only lands when a sync runs, so trends never
accumulate on their own.

This change adds a **daily scheduled full sync**: a worker cron that, once per day, enqueues a
sync for every enabled repository. It guarantees stats refresh at least daily and that the
time-series gets a fresh point each day — independent of webhooks.

## What Changes

- **`ScheduledSyncService`** (application): lists enabled repositories and enqueues a sync for
  each via the existing `RepositoryUseCases.trigger_sync` (which already respects the per-repo
  lock and the pending/running guard, and uses each repo's configured indexing mode). A repo
  already syncing is **skipped**, not duplicated; a failure to enqueue one repo does not stop
  the others. Returns a summary (enqueued / skipped / failed).
- **Worker cron** (`arq` `cron_jobs`): a `scheduled_full_sync` job that runs once per day at a
  configured UTC hour and invokes the service. It only **enqueues** `sync_repository` jobs onto
  the same queue the worker already drains, so the daily fan-out is absorbed by the existing
  concurrency limit and per-repo locks rather than running all syncs at once.
- **Config**: `scheduled_sync_enabled` (default on) and `scheduled_sync_hour` / `scheduled_sync_minute`
  (default 03:00 UTC, off-peak). When disabled, no cron is registered.

### Non-goals (future changes)

- Per-repository custom schedules or cadences (this is one org-wide daily run).
- Sub-daily polling intervals (webhooks remain the near-real-time path).
- Backfilling historical snapshots (the time-series stays forward-only).
- A UI to configure or trigger the schedule (it is env-configured; manual per-repo sync already exists).

## Capabilities

### Modified Capabilities (additive delta)

- `repository-sync`: ADDED — a scheduled daily full sync of all enabled repositories.

## Impact

- **Data model**: none.
- **Code**: new `ScheduledSyncService`, a worker cron entry + coroutine, three config fields.
  Reuses `trigger_sync`, the queue, per-repo locks, and the sync pipeline unchanged.
- **Dependencies**: none new (`arq.cron` is already available).
- **Security**: no new surface; runs inside the worker with the same credentials the manual/
  webhook sync already uses. No API endpoint added.
- **Load**: the daily run enqueues one job per enabled repo; the existing `max_jobs` cap and
  per-repo locks spread the work and prevent overlap with in-flight syncs. Off-peak default hour.
- **Ops**: deploy the worker with the new cron; set `SCHEDULED_SYNC_HOUR` if a different time is
  wanted. Verifiable by observing enqueued jobs / fresh `computed_at` + a new daily snapshot.
