# mcp-interface — intelligence tools reject un-indexed repos

## ADDED Requirements

### Requirement: Intelligence tools reject un-indexed repositories
The MCP engineering-intelligence and delivery tools SHALL reject a repository that is not indexed
(disabled), returning a structured not-indexed result rather than its stale metrics.

#### Scenario: Health tool on a disabled repository
- **GIVEN** a disabled repository
- **WHEN** `mnemosyne_get_repository_health` is called for it
- **THEN** the tool SHALL return a not-indexed error result
