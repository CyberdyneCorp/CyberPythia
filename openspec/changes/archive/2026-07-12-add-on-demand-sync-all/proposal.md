# On-demand "sync all"

## Why

Manual sync is per-repository only; the whole enabled set syncs only via the
nightly job. Re-syncing an organization on demand (e.g. after granting the App a
new permission, or after an indexing-mode change) means clicking Sync on every
repo one at a time. There's no one-click way to trigger a full sync now.

## What changes

An admin can trigger an on-demand sync of all enabled repositories, optionally
scoped to one organization, from the dashboard — reusing the same per-repo
enqueue path the nightly job uses (per-repo lock skips already-running syncs;
one failure doesn't stop the rest). Returns how many were enqueued vs skipped.

## Impact

- Application: `RepositoryUseCases.sync_all(organization?)`.
- REST: `POST /api/v1/repos/sync-all` (admin, optional `organization`).
- Web: a "Sync now" action per organization on the Connections panel.
