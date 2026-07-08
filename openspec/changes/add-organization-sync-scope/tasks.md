# Tasks: add-organization-sync-scope

> Org-level sync scope, fail-open. Typed; unit coverage > 90%; ruff + mypy --strict clean.
> Reuse discovery + the scheduled services. No seeding (unknown org = in scope).

## 1. Domain + persistence

- [x] 1.1 `Organization` entity (login, sync_enabled) + `OrganizationPort` (upsert_many preserving flags, list_all, set_enabled, disabled_logins). `organizations` table (login unique) + Postgres adapter + Alembic `0006`. Integration test (upsert preserves flag, set_enabled, disabled_logins).

## 2. Discovery upsert + enforcement

- [x] 2.1 `RepositoryUseCases.discover` upserts an Organization for each distinct repo owner (default `default_org_sync_enabled`, preserve existing). Unit test.
- [x] 2.2 `ScheduledSyncService`: load disabled org logins; skip repos whose owner is disabled (count as skipped). Unit tests: disabled org skipped, enabled/unknown synced.
- [x] 2.3 `ScheduledDiscoveryService`: do not auto-enable a new repo whose owner is disabled. Unit test.
- [x] 2.4 Config `default_org_sync_enabled: bool = True`. Compose the org port + wire into discover + both scheduled services.

## 3. REST

- [x] 3.1 `GET /api/v1/github/organizations` (AdminCaller) -> orgs with sync_enabled + total/enabled repo counts; `PATCH /api/v1/github/organizations/{login}` (AdminCaller) -> set flag. Schemas + mapping. Interface tests incl. non-admin 403 + unknown-login handling.

## 4. Web

- [x] 4.1 Models + `GitHubApi.organizations()/setOrganizationSync()`; `ConnectionsViewModel.loadOrganizations()/toggleOrganization()`. VM unit test.
- [x] 4.2 Organizations panel on the GitHub Connection page (per-org counts + sync toggle).

## 5. Docs, gate, deploy, verify

- [x] 5.1 Docs: org scope in `docs/deploy-coolify.md` + README.
- [ ] 5.2 Full gate (ruff, mypy --strict, unit >= 90%, integration, openspec --strict, web build + tests, docker build). Deploy migration + code. Verify: list orgs live, disable one, confirm a scheduled/dry run skips its repos; a BDD or interface assertion for the skip.
