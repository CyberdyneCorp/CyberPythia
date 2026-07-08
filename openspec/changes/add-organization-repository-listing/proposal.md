# Proposal: add-organization-repository-listing

## Why

A single credential spans many organizations (e.g. `CyberdyneCorp`, `aminitech`, `EpicGames`, …).
Discovery already stores every repository the credential can read, but neither the API, the MCP
tools, nor the Repositories dashboard let a user or agent **scope the list to one organization**.
On a 345-repo install that makes "show me CyberdyneCorp's repositories" impossible without manual
scanning. This adds organization filtering across REST, MCP, and the web dashboard.

## What Changes

- **REST**: `GET /api/v1/repos` gains an optional `organization` query parameter that filters the
  result to repositories whose owner matches (case-insensitive). Combines with the existing
  `enabled_only` and pagination.
- **MCP** (new tools, behind the existing bearer + entitlement):
  - `mnemosyne_list_organizations` — the distinct organizations Mnemosyne has discovered, each with
    total and indexed repository counts, so an agent can enumerate the orgs it can read.
  - `mnemosyne_list_organization_repositories` — every repository Mnemosyne has discovered in a
    given organization (the ones the credential can read), each with its indexing status and sync
    freshness.
- **Web**: an **organization filter** dropdown on the Repositories dashboard, alongside the text
  filter, populated from the loaded repositories' owners.

### Non-goals (future changes)

- A live GitHub call to enumerate an org's repos beyond what discovery has already stored (the
  discovered set already reflects exactly what the credential can read; run discovery to refresh).
- Per-organization pagination semantics beyond the existing page/page_size.
- Changing what "indexed" means or the sync scope (this is read-only listing/filtering).

## Capabilities

### Modified Capabilities (additive deltas)

- `rest-api`: ADDED — an `organization` filter on the repositories list.
- `mcp-interface`: ADDED — tools to list organizations and an organization's repositories.
- `web-ui`: ADDED — an organization filter on the Repositories dashboard.

## Impact

- **Data model**: none.
- **Code**: `RepositoryUseCases.list_repositories` gains an `organization` filter; one REST query
  param; two MCP tools reading the existing repositories store; a dropdown + view-model filter on
  the web dashboard.
- **Dependencies**: none.
- **Security**: read-only; REST list stays behind the `mnemosyne` entitlement, MCP tools behind the
  same bearer + entitlement. Exposes repository names/metadata already visible in the list.
- **Performance**: filtering is over the already-loaded repositories (in-memory / a bounded query);
  no extra GitHub calls.
