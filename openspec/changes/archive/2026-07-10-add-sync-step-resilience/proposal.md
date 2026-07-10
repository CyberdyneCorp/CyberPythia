# Sync step resilience

## Why

A sync marks the whole job `failed` if *any* step fails, and only advances
`last_synced_at` on a fully-successful job. So a failure in an enrichment step —
source-code capture or embeddings, which depend on external services and large
inputs — flips an otherwise-good sync to `failed` and leaves the repository
looking un-synced, even though metadata, docs, issues, PRs, and the file tree
all succeeded and their data was persisted. This happened to
`CyberdyneCorp/CyberCadKernel`: an oversized embedding chunk failed the
embeddings step and the whole sync read as `failed`.

## What changes

Classify steps as **essential** or **best-effort**:

- **Essential**: metadata, docs, OpenSpec, issues, pull requests, file tree,
  metrics — the intelligence-bearing data.
- **Best-effort**: source code and embeddings — search enrichment.

Sync outcome becomes:

- all steps succeed → `succeeded`
- an essential step fails → `failed`
- only best-effort steps fail → **`degraded`** (a new status)

`last_synced_at` advances when all essential steps succeed — i.e. for both
`succeeded` and `degraded` — so a flaky enrichment step no longer makes a
repository look un-synced. Failed and degraded steps are still recorded and
visible per-step.

## Impact

- Data model: new `SyncStatus.DEGRADED`; no schema change (status is a string
  column).
- Behavior: `finish()` classification + `last_synced_at` gating.
- Surfaces: `/admin/sync-jobs` and the web sync-activity table show `degraded`.
