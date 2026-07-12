# History retention (prune old snapshots)

## Why

The metrics and readiness time-series grow ~1 row per repository per day forever;
`prune()` is a stub that returns 0, so nothing bounds them. The existing spec
called for downsampling, but that was never built. Unbounded growth bloats the
database and its backups.

## What changes

Implement **delete-based retention**: on the daily scheduled run, delete
snapshots older than a configurable window from both the metrics and readiness
per-repository daily series (`history_retention_days`, default 365 — comfortably
beyond the windows the analytics read). Retention runs off the request path and
never fails the scheduled run. (Coarser-granularity downsampling of very old
points is a possible future refinement; deletion is sufficient to bound growth.)

## Impact

- `MetricsHistoryPort.prune` / `ReadinessHistoryPort.prune` delete rows older
  than the window (was a no-op stub / absent).
- Config: `history_retention_days` (default 365; 0 disables).
- Worker: the daily job prunes both series after recording.
- metrics-history spec: retention is delete-based over the daily series.
