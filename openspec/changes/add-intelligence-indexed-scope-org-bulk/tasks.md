# Tasks: add-intelligence-indexed-scope-org-bulk

> Typed; unit coverage > 90%; ruff + mypy --strict clean. Branch -> PR -> merge.

## 1. Intelligence scoped to indexed
- [x] 1.1 `IntelligenceService._repo` + `DeliveryIntelligenceService._repo` reject disabled repos (raise UnknownResourceError -> 404). Unit tests (disabled -> raises; portfolio/scorecard already exclude — assert).
- [x] 1.2 Interface: per-repo REST intelligence on a disabled repo -> 404; MCP health tool on a disabled repo -> not-indexed error (lock in). Tests.

## 2. Org-scoped bulk
- [x] 2.1 `bulk_update_selection(..., organization=None)` applies to all repos in an org. `RepositorySelectionBulkRequest`: `repository_ids` optional + `organization` optional + validator (one required). Endpoint passes organization. Unit + interface tests (org path, neither -> 422).

## 3. Web
- [x] 3.1 `GitHubApi.bulkSelectionByOrg(login, enabled, mode?)`; `ConnectionsViewModel.indexOrganization(login, enabled, mode)`. VM test.
- [x] 3.2 Organizations panel: Index-all / Un-index-all + mode select per org; refresh counts.

## 4. Gate
- [ ] 4.1 ruff, mypy --strict, unit >= 90%, integration, openspec --strict, web build + tests. Deploy after merge; verify a disabled repo drops from REST + MCP intelligence and an org un-index works live.
