# Tasks

- [x] 1. Add `SyncStatus.DEGRADED`
- [x] 2. Classify best-effort steps (source_code, embeddings); `finish()` → succeeded/failed/degraded
- [x] 3. Advance `last_synced_at` on essential success (succeeded or degraded)
- [x] 4. Tests: finish() classification, last_synced_at gating, degraded end-to-end
