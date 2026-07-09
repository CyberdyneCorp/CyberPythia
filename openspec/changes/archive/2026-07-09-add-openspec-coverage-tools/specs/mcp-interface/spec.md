# mcp-interface Specification

## ADDED Requirements

### Requirement: OpenSpec coverage MCP tools

The MCP server SHALL expose `mnemosyne_list_repositories_with_openspec` and
`mnemosyne_list_repositories_missing_openspec`, each taking an `organization` and
returning that organization's indexed repositories that have (respectively lack)
OpenSpec, based on the canonical `has_openspec` signal from the latest sync. Each
repository entry SHALL include its full name and last-synced time.

#### Scenario: Repositories with OpenSpec
- **WHEN** an entitled caller invokes `mnemosyne_list_repositories_with_openspec` for an organization
- **THEN** it SHALL return that organization's indexed repositories whose latest sync detected OpenSpec

#### Scenario: Repositories missing OpenSpec
- **WHEN** an entitled caller invokes `mnemosyne_list_repositories_missing_openspec` for an organization
- **THEN** it SHALL return that organization's indexed repositories with no detected OpenSpec (including never-synced repositories)
