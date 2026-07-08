# Proposal: add-intelligence-indexed-scope-org-bulk

## Why

Two related gaps around un-indexing:

1. **Intelligence should ignore repositories that are no longer indexed.** The portfolio overview
   and delivery scorecard already restrict to enabled repositories, and the MCP intelligence tools
   already reject a repository that isn't enabled. But the **per-repository REST intelligence
   endpoints** (`/intelligence/repositories/{id}/health`, `…/delivery`, `…/flow`, etc.) only check
   that the repository exists — so a repository an admin has **disabled** still returns its stale
   persisted health/delivery data. That's inconsistent with MCP and violates "don't count
   un-indexed repos."

2. **Un-indexing a whole organization is tedious.** Bulk enable/disable exists on the Repositories
   dashboard (over the current filter), but the Organizations view — the natural place to say
   "stop indexing EpicGames" — has only the sync toggle, not a way to index/un-index all of an
   org's repositories at once.

## What Changes

- **Intelligence scoped to indexed repos**: the per-repository intelligence services SHALL treat a
  **disabled** repository as not indexed and reject it (same "not indexed / not found" outcome the
  MCP tools already return). Portfolio + scorecard already exclude disabled repos (unchanged); this
  makes the per-repo REST endpoints consistent.
- **Org-scoped bulk selection**: `POST /api/v1/repos/selection` accepts an `organization` as an
  alternative to `repository_ids` — applying the enable/disable (+ optional mode) to **all
  repositories in that organization** in one batched write. `RepositoryUseCases.bulk_update_selection`
  gains the org path.
- **Web**: the Organizations panel gains **Index all** / **Un-index all** actions per organization
  (with a mode for indexing), calling the org-scoped bulk; the panel's counts update in place.

### Non-goals (future changes)

- Org-level intelligence aggregation (intelligence stays repo-level; an org with no indexed repos
  simply doesn't appear).
- Deleting persisted metrics for un-indexed repos (they are retained but no longer surfaced; a
  future cleanup could prune them).
- Bulk actions on the Intelligence dashboard itself (the org view is the chosen home).

## Capabilities

### Modified Capabilities (additive deltas)

- `engineering-intelligence`: ADDED — per-repository intelligence excludes un-indexed repositories.
- `mcp-interface`: ADDED — the intelligence tools reject un-indexed repositories (locks in existing behavior).
- `rest-api`: ADDED — organization-scoped bulk repository selection.
- `web-ui`: ADDED — per-organization Index-all / Un-index-all controls.

## Impact

- **Data model**: none.
- **Code**: an `enabled` guard in both intelligence services' repo lookup; an `organization` path in
  `bulk_update_selection` + the bulk request schema; per-org buttons in the Organizations panel.
- **Dependencies**: none.
- **Security**: unchanged (per-repo intelligence stays entitled; bulk selection stays admin-only).
- **Behaviour**: disabling a repo (or un-indexing an org) immediately removes it from all
  intelligence surfaces (portfolio, scorecard, per-repo REST + MCP). Re-enabling restores it.
