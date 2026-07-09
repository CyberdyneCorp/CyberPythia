# Tasks

- [x] 1. `CapabilitiesService.organization_openspec_coverage(org)` — partition enabled org repos by the metrics `has_openspec` signal; return with/without briefs + total + coverage
- [x] 2. MCP: `mnemosyne_list_repositories_with_openspec` + `mnemosyne_list_repositories_missing_openspec`
- [x] 3. REST: `GET /api/v1/intelligence/organizations/{org}/openspec-coverage`
- [x] 4. Tests: service (with/without/coverage/never-synced), MCP tools, REST endpoint
- [x] 5. Docs: mcp-consumers tool table
