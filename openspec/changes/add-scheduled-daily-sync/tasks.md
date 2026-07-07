# Tasks: add-scheduled-daily-sync

> Small operational change. Reuse trigger_sync, the queue, and per-repo locks. Keep the
> domain pure; unit coverage > 90%; ruff + mypy --strict clean.

## 1. Application

- [x] 1.1 `ScheduledSyncService.run()` — list enabled repositories and enqueue a sync for each via `trigger_sync(repo.id, triggered_by="scheduler")`; catch `SyncAlreadyRunningError` (skip) and any other error (log + continue); return an `{enqueued, skipped, failed}` summary. Unit tests: all-enqueued, skip-already-running, one-failure-does-not-stop-others, disabled-repos-excluded.

## 2. Config + worker cron

- [x] 2.1 Config: `scheduled_sync_enabled: bool = True`, `scheduled_sync_hour: int = 3`, `scheduled_sync_minute: int = 0`. Unit test defaults + env override.
- [x] 2.2 Worker: `scheduled_full_sync(ctx)` coroutine builds the service from the container and runs it; register `WorkerSettings.cron_jobs` with `arq.cron` at the configured hour/minute only when enabled. Unit test the coroutine (fake container) + that the cron list is empty when disabled.

## 3. Docs, gate, deploy, verify

- [x] 3.1 Docs: note the daily schedule + env vars in `docs/deploy-coolify.md` and the README updates section.
- [ ] 3.2 Full gate: ruff, mypy --strict, unit ≥ 90%, integration, `openspec validate --all --strict`, docker build. Deploy the worker. Verify the cron is registered (log on startup) and that a manual invocation of `scheduled_full_sync` enqueues syncs for the enabled repos.
