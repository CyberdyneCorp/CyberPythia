# mcp-interface Specification

## ADDED Requirements

### Requirement: Organization-scoped intelligence MCP tools

The MCP server SHALL expose `mnemosyne_get_organization_intelligence` returning a
one-call rollup for an organization (repositories, scored count, average and median
health, grade distribution, at-risk milestone total, throughput directions, and the
most-active / abandoned / bug-heavy lists). `mnemosyne_get_portfolio_overview` and
`mnemosyne_get_delivery_scorecard` SHALL accept an optional `organization` argument
that scopes the result to that organization's indexed repositories.

#### Scenario: Organization rollup
- **WHEN** an entitled caller invokes `mnemosyne_get_organization_intelligence` for an organization
- **THEN** it SHALL return the aggregated health and delivery rollup for that organization's indexed repositories

#### Scenario: Scoped portfolio
- **WHEN** an entitled caller passes `organization` to `mnemosyne_get_portfolio_overview` or `mnemosyne_get_delivery_scorecard`
- **THEN** the response SHALL include only repositories owned by that organization

### Requirement: Cross-repository MCP tools

The MCP server SHALL expose tools that operate across many repositories at once:
`mnemosyne_search_all` (search documentation, code, or issues across all indexed
repositories or one organization), `mnemosyne_find_stale_issues_across_repos` and
`mnemosyne_find_stale_prs_across_repos` (open items with no activity beyond a
threshold, oldest first), `mnemosyne_find_repositories` (fuzzy resolve a name to
indexed repositories), `mnemosyne_get_recent_activity` (recently synced repositories
plus latest updated issues and pull requests), and `mnemosyne_get_repository_metrics`
(raw computed metrics snapshot). Results that span repositories SHALL carry each
item's repository identity.

#### Scenario: Global search
- **WHEN** an entitled caller calls `mnemosyne_search_all` with a query and a `kind` of docs, code, or issues
- **THEN** it SHALL return ranked matches drawn from all indexed repositories (or the given organization), each carrying its repository full name

#### Scenario: Invalid search kind
- **WHEN** `mnemosyne_search_all` is called with a `kind` other than docs, code, or issues
- **THEN** it SHALL return a structured error rather than results

#### Scenario: Portfolio-wide stale triage
- **WHEN** an entitled caller calls `mnemosyne_find_stale_issues_across_repos` (optionally scoped to an organization)
- **THEN** it SHALL return open issues stale beyond the threshold across those repositories, oldest first

#### Scenario: Resolve a repository by fuzzy name
- **WHEN** an entitled caller calls `mnemosyne_find_repositories` with a partial name
- **THEN** it SHALL return matching indexed repositories ranked by relevance

### Requirement: Capability and feature MCP tools

The MCP server SHALL expose `mnemosyne_get_repository_capabilities` (a project's
capabilities — OpenSpec spec areas — documentation topics, open/closed issue counts,
bug count, and pull-request counts), `mnemosyne_get_organization_capabilities` (the
union of capabilities across an organization's repositories, total open bugs, and a
per-project brief), and `mnemosyne_generate_feature_document` (a grounded Markdown
document of the project's features synthesized from indexed context, with citations).

#### Scenario: Repository capabilities in one call
- **WHEN** an entitled caller invokes `mnemosyne_get_repository_capabilities` for a repository
- **THEN** it SHALL return its capabilities, documentation topics, bug count, and issue/PR counts without further calls

#### Scenario: Organization capabilities
- **WHEN** an entitled caller invokes `mnemosyne_get_organization_capabilities` for an organization
- **THEN** it SHALL return the union of capabilities across its repositories plus total open bugs and per-project briefs

#### Scenario: Feature document
- **WHEN** an entitled caller invokes `mnemosyne_generate_feature_document` for a repository
- **THEN** it SHALL return a Markdown features document grounded in indexed documentation, OpenSpec, and code, with source citations
