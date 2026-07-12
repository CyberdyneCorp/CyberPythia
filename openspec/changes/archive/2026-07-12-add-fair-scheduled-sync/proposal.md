# Fair, rate-aware scheduled sync

## Why

The scheduled sync enqueues enabled repositories in a fixed order (by name). When
the GitHub rate budget is exhausted partway — common for a large org in a heavy
indexing mode — the same alphabetically-early repositories consume the budget
every run and the later ones fail-fast every time, so they **never** sync
(starvation). Observed: 14/50 repos synced, the rest rate-limited each night.

## What changes

- **Fairness** — the scheduled run orders repositories **least-recently-synced
  first** (never-synced before oldest before newest). A repo that failed (its
  `last_synced_at` stayed stale) rises to the front of the next run, so every
  repository is eventually synced even under sustained budget pressure.
- **Per-run cap (rate-aware knob)** — an optional `scheduled_sync_max_repos_per_run`
  bounds how many repositories a single run attempts (0 = unlimited, today's
  behavior). With fairness ordering, a capped run deterministically works through
  the whole org across successive runs instead of relying on rate-limit failures.
  Deferred repositories are logged.

## Impact

- `ScheduledSyncService`: least-recently-synced ordering + per-run cap; the same
  ordering is applied to on-demand `sync_all` for consistency.
- Config: `scheduled_sync_max_repos_per_run` (default 0).
