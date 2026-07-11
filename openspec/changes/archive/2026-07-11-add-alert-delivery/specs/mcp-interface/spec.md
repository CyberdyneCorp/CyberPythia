# mcp-interface Specification

## ADDED Requirements

### Requirement: Organization digest MCP tool

The MCP server SHALL expose `mnemosyne_get_organization_digest(organization)`
returning the organization's attention digest (readiness regressions, stale
issues/PRs, at-risk milestones, and a summary line).

#### Scenario: Digest tool
- **WHEN** an entitled caller invokes `mnemosyne_get_organization_digest`
- **THEN** it SHALL return the digest sections and summary
