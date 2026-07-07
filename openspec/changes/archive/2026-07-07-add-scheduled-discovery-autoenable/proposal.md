# Proposal: add-scheduled-discovery-autoenable

## Why

The daily scheduled sync re-syncs every **enabled** repository, but a repo is only enabled
after an admin selects it. In practice a connection can see far more repos than are enabled
(e.g. 345 discovered vs. 2 enabled), and **newly-created** repos never get indexed until someone
re-runs discovery and enables them by hand. The goal is coverage that stays current on its own:
each day, pick up repositories the connections can see and **auto-enable the new ones**.

Crucially, this must **not fight the admin**: a repo an admin has deliberately *disabled* should
stay disabled. So auto-enable applies **only to repositories that are newly discovered** (a
github id not seen before) — existing repos keep whatever enabled state they have.

## What Changes

- **`ScheduledDiscoveryService`** (application): for every connection, run the existing discovery
  (which reconciles repo metadata, preserving each repo's current enabled state); detect
  repositories whose github id was **not present before** this run; and auto-enable those new,
  **non-archived** repos in a configured indexing mode. Returns a summary
  (`discovered`, `newly_enabled`, `skipped_archived`).
- **Daily job chaining**: the existing daily worker cron runs discovery + auto-enable **first**,
  then the full sync of all enabled repos — so a new repo is discovered, enabled, and synced in
  the same nightly run.
- **Config**: `scheduled_discovery_enabled` (default on), `auto_enable_new_repos` (default on),
  `auto_enable_mode` (default `project_intelligence` — docs/OpenSpec/issues/PRs/metrics, no
  source-code embeddings, cheap at scale), and `auto_enable_archived` (default off).

### Non-goals (future changes)

- Auto-enabling **existing** discovered-but-disabled repos (that is a one-time admin bulk action,
  intentionally out of the automated path so manual disables are never overridden).
- Re-enabling a repo an admin disabled (explicitly prevented — only brand-new repos are enabled).
- Per-repo or per-connection mode overrides for auto-enable (one org-wide default mode).
- Repo-level allow/deny lists for what may be auto-enabled (all newly-seen non-archived repos qualify).

## Capabilities

### Modified Capabilities (additive delta)

- `repository-sync`: ADDED — scheduled repository discovery with auto-enable of newly-appearing
  non-archived repositories, chained ahead of the daily full sync.

## Impact

- **Data model**: none.
- **Code**: new `ScheduledDiscoveryService`, four config fields, and the daily cron coroutine
  calling discovery before the sync fan-out. Reuses `discover` + `update_selection` unchanged.
- **Dependencies**: none new.
- **Security / access**: auto-enable indexes content the connection's credential can already read;
  it only ever *adds* newly-seen non-archived repos and never overrides a manual disable. Runs in
  the worker with the existing credentials; no new API surface.
- **Load / cost**: `project_intelligence` (default) captures docs/OpenSpec/issues/PRs/metrics with
  **no per-file source embeddings**, so a large auto-enabled set stays affordable; the daily fan-out
  is still bounded by the worker's `max_jobs` and per-repo locks. A large first sweep can approach
  GitHub rate limits on a personal PAT — mitigated by the existing retry/backoff and by moving to a
  fine-grained org PAT or GitHub App (higher limits) for production.
- **Ops**: set `AUTO_ENABLE_MODE` to change the default mode, or `AUTO_ENABLE_NEW_REPOS=false` /
  `SCHEDULED_DISCOVERY_ENABLED=false` to turn parts off. The one-time enable of the *existing*
  discovered repos is an admin action (bulk `PATCH /api/v1/repos/{id}`), separate from this change.
