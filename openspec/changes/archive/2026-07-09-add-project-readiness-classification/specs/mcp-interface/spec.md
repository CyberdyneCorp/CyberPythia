# mcp-interface Specification

## ADDED Requirements

### Requirement: Readiness MCP tools

The MCP server SHALL expose `mnemosyne_get_repository_readiness(full_name)` returning a
repository's gate (MVP/READY/DONE) with the per-check met/missing/unknown breakdown, and
`mnemosyne_get_organization_readiness(organization)` returning the gate distribution plus
each repository's gate and missing-for-READY checks.

#### Scenario: Repository readiness
- **WHEN** an entitled caller invokes `mnemosyne_get_repository_readiness` for a repository
- **THEN** it SHALL return the gate and per-check breakdown

#### Scenario: Organization readiness distribution
- **WHEN** an entitled caller invokes `mnemosyne_get_organization_readiness` for an organization
- **THEN** it SHALL return per-gate counts and each repository's gate and gaps
