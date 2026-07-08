# Proposal: add-organization-sync-scope

## Why

A single PAT (or GitHub App) can see repositories across **many organizations** — e.g.
`CyberdyneCorp`, `EpicGames`, `github-beta`, `PacktPublishing`, `aminitech`. Today discovery
enables and syncs across **all** of them, so an admin who only cares about one org (say
`CyberdyneCorp`) has no way to scope Mnemosyne to it. They end up indexing — and nightly
re-syncing — hundreds of repos they don't want, burning GitHub rate limit and OpenAI spend.

This change gives the admin an **organization-level sync toggle**: Mnemosyne tracks each
organization it has seen, and the admin turns sync on or off per org. Scheduled discovery and
the nightly sync then skip repositories in disabled organizations.

The model is **fail-open**: an organization not yet recorded (or left enabled) syncs exactly as
today, so nothing changes until the admin explicitly disables an org. No data migration seeding
and no surprise disabling of the repos already being indexed.

## What Changes

- **Organization tracking**: a new `organizations` table + `Organization` entity, keyed by
  GitHub login, each with a `sync_enabled` flag. **Discovery upserts** an organization for every
  repository owner it sees; a newly-seen org defaults to enabled (configurable), and an existing
  org's flag is preserved.
- **Enforcement (fail-open)**: scheduled discovery/sync compute the set of **disabled** org
  logins (orgs explicitly toggled off) and skip any repository whose owner is in that set:
  - `ScheduledSyncService` does not enqueue a sync for a repository in a disabled org (counted as
    skipped in the run summary).
  - `ScheduledDiscoveryService` does not auto-enable a newly-discovered repository in a disabled org.
  A repository whose org is enabled or unknown is unaffected.
- **Admin management**:
  - `GET /api/v1/github/organizations` — list organizations with their `sync_enabled` state and
    repository counts (total / enabled).
  - `PATCH /api/v1/github/organizations/{login}` — enable or disable sync for an organization.
- **Web UI**: an **Organizations** panel on the GitHub Connection page listing each org with a
  sync toggle and its repo counts.
- **Config**: `default_org_sync_enabled` (default `true`) — the flag a newly-discovered org gets.

### Non-goals (future changes)

- Per-organization indexing-mode or schedule (one global mode/schedule still applies).
- Team- or repository-glob-level scoping within an org (org granularity only).
- Automatically **disabling/re-syncing** already-enabled repositories when their org is turned off
  beyond skipping them in the scheduled paths (a manual bulk-disable remains an admin action; the
  scheduled sync simply stops touching them).
- Manual single-repo sync honoring the org toggle (an explicit admin action stays allowed; the
  toggle governs the automated discovery/sync paths).

## Capabilities

### New / Modified Capabilities (additive deltas)

- `github-connection`: ADDED — organizations are tracked with a per-org sync-enabled flag that an
  admin can toggle.
- `repository-sync`: ADDED — scheduled discovery and sync skip repositories in sync-disabled
  organizations (fail-open for unknown/enabled orgs).
- `rest-api`: ADDED — list organizations and toggle an organization's sync.
- `web-ui`: ADDED — an Organizations panel with per-org sync toggles.

## Impact

- **Data model**: one new table `organizations` (login unique, `sync_enabled`). One Alembic
  migration `0006`. No seeding required (fail-open).
- **Code**: `Organization` entity + `OrganizationPort` + Postgres adapter; discovery upserts orgs;
  `ScheduledSyncService`/`ScheduledDiscoveryService` gain a disabled-org filter; two REST endpoints;
  a Svelte Organizations panel.
- **Dependencies**: none new.
- **Security**: admin-only management endpoints; read-only listing exposes org names + counts, no
  repository content.
- **Behaviour**: default-on / fail-open, so the deploy changes nothing until an admin disables an
  org. Disabling an org immediately narrows the next nightly run (its repos are skipped).
- **Cost**: disabling large orgs is the primary lever to cut the nightly GitHub/OpenAI load on a
  multi-org PAT.
