# mcp-interface — organization listing tools

## ADDED Requirements

### Requirement: Organization listing MCP tools
The MCP server SHALL expose, behind the same bearer authentication and `mnemosyne` entitlement as
existing tools:

- `mnemosyne_list_organizations` — the distinct organizations Mnemosyne has discovered, each with
  total and indexed repository counts.
- `mnemosyne_list_organization_repositories` — every repository discovered in a given organization,
  each with its full name, indexing status, and sync freshness.

#### Scenario: Agent enumerates organizations
- **WHEN** `mnemosyne_list_organizations` is called by an authenticated, entitled caller
- **THEN** the tool SHALL return the discovered organizations with their repository counts

#### Scenario: Agent lists an organization's repositories
- **WHEN** `mnemosyne_list_organization_repositories` is called with an organization
- **THEN** the tool SHALL return the repositories discovered in that organization with indexing status

#### Scenario: Unauthenticated call rejected
- **GIVEN** a caller without a valid bearer token
- **WHEN** either tool is called
- **THEN** the call SHALL be rejected as unauthenticated
