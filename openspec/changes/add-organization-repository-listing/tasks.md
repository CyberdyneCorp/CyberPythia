# Tasks: add-organization-repository-listing

> Additive org filtering across REST, MCP, and web. Typed; unit coverage > 90%; ruff + mypy
> --strict clean. Branch -> PR -> merge.

## 1. Backend

- [x] 1.1 `RepositoryUseCases.list_repositories(organization=None)` — filter by owner (case-insensitive). Unit test.
- [x] 1.2 REST: `organization` query param on `GET /api/v1/repos`. Interface test (filter + no-filter).
- [x] 1.3 MCP: `mnemosyne_list_organizations` (distinct owners + total/indexed counts) + `mnemosyne_list_organization_repositories(organization)` (repos in org w/ indexing status). Interface tests incl. unauth rejection.

## 2. Web

- [x] 2.1 `RepositoryListViewModel`: `organizationFilter` state + `organizations` getter (distinct owners) + `filtered` honors both text + org. VM unit tests.
- [x] 2.2 Repositories dashboard: an organization `<select>` beside the text filter.

## 3. Docs, gate

- [x] 3.1 Docs: note the org filter + MCP tools in README / docs/mcp-consumers.md.
- [x] 3.2 Gate: ruff, mypy --strict, unit >= 90%, integration, openspec --strict, web build + tests. (Deploy after merge.)
