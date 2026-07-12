# Tasks

- [x] 1. Config: history_retention_days (default 365; 0 disables)
- [x] 2. MetricsHistoryPort.prune(retention_days) deletes old rows (+ readiness port + adapter)
- [x] 3. Daily worker prunes both series after recording (best-effort)
- [x] 4. Tests: adapter prune deletes old/keeps recent; disabled=0 no-op; worker invokes prune
