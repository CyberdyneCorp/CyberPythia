# Tasks

- [x] 1. `ReadinessSnapshot` entity + `ReadinessHistoryPort`
- [x] 2. Model row + migration 0008 (`repository_readiness_snapshots`)
- [x] 3. Postgres adapter: record (daily upsert), list_for_repository, latest-two-by-repo
- [x] 4. `ReadinessService`: record_snapshots, repository_history, organization_regressions
- [x] 5. Composition wiring + daily worker records snapshots after sync
- [x] 6. REST: /repos/{id}/readiness-history, /organizations/{org}/readiness-regressions
- [x] 7. MCP: get_readiness_history, get_readiness_regressions
- [x] 8. Tests: adapter (upsert), regressions logic, endpoints/tools
