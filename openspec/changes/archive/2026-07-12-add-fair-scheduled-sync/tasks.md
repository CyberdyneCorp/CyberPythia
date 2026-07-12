# Tasks

- [x] 1. ScheduledSyncService orders enabled repos least-recently-synced first
- [x] 2. Optional per-run cap (scheduled_sync_max_repos_per_run, default 0=unlimited) + deferred log
- [x] 3. Apply the same ordering to on-demand sync_all
- [x] 4. Config setting + composition wiring
- [x] 5. Tests: ordering, cap defers remainder, fairness across runs
