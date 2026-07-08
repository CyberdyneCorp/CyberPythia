# Proposal: add-bulk-repository-selection

## Why

Enabling or disabling indexing is per-repository today (one checkbox per card). With hundreds of
discovered repositories — and now an organization filter — an admin who wants to "index every
CyberdyneCorp repo" or "clear all of these" has to click each card. That's tedious and, done
naively client-side, would fire hundreds of PATCH requests (and audit events). This adds a single
**bulk selection** operation and Enable-all / Disable-all controls that act on the currently
filtered set.

## What Changes

- **REST**: `POST /api/v1/repos/selection` (admin) — set `enabled` (and optional `indexing_mode`)
  for a list of repository ids in one request; returns the number updated. One audit event, one
  transaction (batched write), no per-repo round trips.
- **Web**: **Enable all** / **Disable all** buttons on the Repositories dashboard that apply to the
  **filtered** repositories (so they respect the organization and text filters), with a small mode
  selector for the enable action. The dashboard updates in place.

### Non-goals (future changes)

- Selecting an arbitrary subset via per-row checkboxes (bulk acts on the current filter; narrow the
  filter to scope it).
- Bulk-triggering syncs (this only sets the indexing selection; the scheduled/manual sync paths run
  as usual).
- Per-organization default modes (one mode is chosen for the bulk enable).

## Capabilities

### Modified Capabilities (additive deltas)

- `rest-api`: ADDED — a bulk repository-selection endpoint.
- `web-ui`: ADDED — Enable-all / Disable-all controls scoped to the current filter.

## Impact

- **Data model**: none.
- **Code**: `RepositoryUseCases.bulk_update_selection`; one REST endpoint + request schema; a
  view-model bulk action + two buttons on the dashboard.
- **Dependencies**: none.
- **Security**: admin-only (same guard as the per-repo PATCH); one audit event records the bulk
  action and count.
- **Performance**: a single batched `save_many` transaction instead of N requests; capped list size.
