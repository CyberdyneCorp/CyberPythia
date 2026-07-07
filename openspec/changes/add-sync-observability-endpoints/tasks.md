# Tasks: add-sync-observability-endpoints

> Adds run-history persistence + two admin read endpoints. Typed; unit coverage > 90%;
> ruff + mypy --strict clean. Reuse AdminCaller + the sync_jobs adapter.

## 1. Persistence

- [x] 1.1 `SyncRun` entity + `SyncRunPort`; `sync_run_history` table + Postgres adapter (record, list_recent) + Alembic migration `0005`. Integration test on real Postgres.
- [x] 1.2 `SyncJobPort.list_recent(limit)` + Postgres adapter method (order by started_at desc, nulls last) reusing `sync_job_to_entity`. Integration test.

## 2. Cron records the run

- [x] 2.1 The daily cron builds a `SyncRun` from the discovery + sync summaries (timestamps, trigger, counters) and records it. Unit test the coroutine records a run with the right counters.

## 3. Admin endpoints

- [x] 3.1 `GET /api/v1/admin/sync-runs` (AdminCaller) -> recent run summaries; `SyncRunResponse` schema. Interface test incl. non-admin 403.
- [x] 3.2 `GET /api/v1/admin/sync-jobs` (AdminCaller) -> recent jobs with repo name + status + failed-step errors; resolve repo names; `SyncJobSummaryResponse` schema. Interface test incl. a failed (rate-limited) job surfacing its error, and non-admin 403.
- [x] 3.3 Compose ports in `composition.py`; register endpoints on the admin router.

## 4. Docs, gate, deploy, verify

- [x] 4.1 Docs: note the two admin endpoints in `docs/deploy-coolify.md` / README.
- [x] 4.2 Full gate: ruff, mypy --strict, unit >= 90%, integration, `openspec validate --all --strict`, docker build. Deploy migration + code. Verify both endpoints live (admin token) and that non-admin is rejected.
