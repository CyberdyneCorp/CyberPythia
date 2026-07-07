# add-sync-observability-endpoints

Persist each nightly scheduled-run outcome (discovered/newly-enabled/enqueued/skipped/failed) and
add two admin read endpoints — GET /api/v1/admin/sync-runs and GET /api/v1/admin/sync-jobs — so an
admin can watch the daily runs and see which repos failed or were rate-limited. One new table
(sync_run_history), migration 0005; reuses admin auth and the sync_jobs adapter.
