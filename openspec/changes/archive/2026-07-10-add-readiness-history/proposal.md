# Readiness history and regression alerts

## Why

Readiness is currently a snapshot — you can see a repository's gate now, but not
whether it is trending up or slipping. A repository silently dropping from READY
back to MVP (CI removed, tests deleted, bug ratio spiking) is exactly the kind of
regression a PM/PO wants flagged, and there's no way to see it today.

## What changes

Record each repository's readiness gate once per day and expose the trend plus
regressions:

- **History**: a daily readiness snapshot per repository (gate on that day). The
  daily scheduled job records gates after it syncs. Historical readiness cannot
  be back-filled (it depends on file-tree signals not stored per day), so the
  series accrues going forward.
- **Regressions (alerts)**: an organization view of repositories whose latest
  gate is *worse* than their previous recorded gate (DONE→READY, READY→MVP,
  DONE→MVP), with the from/to gates and when it happened.
- **Surfaces**: repository readiness trend and organization regressions over MCP
  and REST.

## Impact

- Data model: new `repository_readiness_snapshots` table (migration; now safe —
  the API applies migrations on boot).
- Worker: the daily job records readiness snapshots after syncing.
- Application: `ReadinessService` gains recording, history, and regression queries.
- MCP + REST: readiness-history and readiness-regressions endpoints.
