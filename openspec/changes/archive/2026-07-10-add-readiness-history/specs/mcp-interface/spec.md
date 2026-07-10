# mcp-interface Specification

## ADDED Requirements

### Requirement: Readiness history MCP tools

The MCP server SHALL expose `mnemosyne_get_readiness_history(full_name)`
returning a repository's dated gate trend, and
`mnemosyne_get_readiness_regressions(organization)` returning repositories whose
latest gate is lower than their previous gate with the previous/current gate and
date.

#### Scenario: Readiness history tool
- **WHEN** an entitled caller invokes `mnemosyne_get_readiness_history` for a repository
- **THEN** it SHALL return the dated gate series

#### Scenario: Readiness regressions tool
- **WHEN** an entitled caller invokes `mnemosyne_get_readiness_regressions` for an organization
- **THEN** it SHALL return repositories whose gate dropped, with previous/current gate and date
