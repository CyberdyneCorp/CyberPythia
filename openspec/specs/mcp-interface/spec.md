# mcp-interface Specification

## Purpose
TBD - created by archiving change add-github-context-memory-core. Update Purpose after archive.
## Requirements
### Requirement: MCP server deployment
The system SHALL run a FastMCP server as a separate service (`mnemosyne-mcp`) from the REST API, sharing the same domain layer, database, and auth capability. The server SHALL use a network transport (streamable HTTP) and SHALL authenticate callers with CyberdyneAuth bearer tokens per the auth capability.

#### Scenario: Unauthenticated MCP client
- **WHEN** an MCP client connects without a valid bearer token
- **THEN** tool invocations SHALL be rejected with an authentication error

### Requirement: Repository tools
The MCP server SHALL expose: `mnemosyne_list_repositories`, `mnemosyne_get_repository_summary`, `mnemosyne_get_repository_tree`. Each SHALL return only repositories that are enabled for indexing and SHALL include sync freshness timestamps.

#### Scenario: Agent lists repositories
- **WHEN** an entitled agent calls `mnemosyne_list_repositories`
- **THEN** it SHALL receive indexed repositories with full name, description, language, mode, and last sync time

### Requirement: Documentation tools
The MCP server SHALL expose: `mnemosyne_get_readme`, `mnemosyne_get_docs_index`, `mnemosyne_search_docs`, `mnemosyne_get_openspec_context`. `mnemosyne_search_docs` SHALL use semantic search; `mnemosyne_get_openspec_context` SHALL return the repository's OpenSpec changes and specs.

#### Scenario: Agent retrieves OpenSpec context
- **WHEN** an agent calls `mnemosyne_get_openspec_context` for a repository with captured OpenSpec changes
- **THEN** it SHALL receive the changes with proposal/tasks/design content and inferred status

### Requirement: Issue and PR tools
The MCP server SHALL expose: `mnemosyne_list_issues`, `mnemosyne_get_issue`, `mnemosyne_search_issues`, `mnemosyne_get_issue_resolution_metrics`, `mnemosyne_list_pull_requests`, `mnemosyne_get_pull_request`, `mnemosyne_get_pr_review_metrics`, `mnemosyne_find_stale_issues`, `mnemosyne_find_stale_prs`.

#### Scenario: Agent queries issue metrics
- **WHEN** an agent calls `mnemosyne_get_issue_resolution_metrics` for a synced repository
- **THEN** it SHALL receive average/median resolution times and stale-issue counts with the metrics timestamp

### Requirement: Context tools
The MCP server SHALL expose: `mnemosyne_build_context_pack` and `mnemosyne_answer_from_repo_context`, delegating to the context-packs capability with identical semantics (mode constraints, citations, insufficient-context behavior).

#### Scenario: Agent builds a context pack before a task
- **WHEN** an agent calls `mnemosyne_build_context_pack` with a repository and task description
- **THEN** it SHALL receive the structured pack (summary, relevant docs/OpenSpec/issues/PRs/files, risks, suggested next steps)

### Requirement: Tool errors are structured
MCP tools SHALL return structured, actionable errors (unknown repository, repository not synced, insufficient entitlement, mode excludes content) rather than free-text failures, so calling agents can branch on them.

#### Scenario: Tool call on unsynced repository
- **WHEN** an agent calls a documentation tool for a repository that has never synced
- **THEN** the error SHALL identify the repository and state that a sync is required

### Requirement: Code MCP tools
The MCP server SHALL expose: `mnemosyne_get_file_content`, `mnemosyne_search_code`, `mnemosyne_get_symbol_context`, `mnemosyne_get_related_files`, and `mnemosyne_explain_repository_structure`. Each SHALL require the `mnemosyne` entitlement and return structured errors; tools that need source content SHALL return a `mode_excludes_content` error for repositories not indexed for code, and `repository_not_synced` for unsynced repositories.

#### Scenario: Agent searches code
- **WHEN** an entitled agent calls `mnemosyne_search_code` for a `code_context` repository
- **THEN** it SHALL receive ranked source-chunk matches with file, symbol, line span, and excerpt

#### Scenario: Code tool on non-code repository
- **WHEN** an agent calls `mnemosyne_get_file_content` or `mnemosyne_search_code` for a repository indexed below `code_context`
- **THEN** the tool SHALL return a `mode_excludes_content` structured error

#### Scenario: Explain repository structure
- **WHEN** an agent calls `mnemosyne_explain_repository_structure` for a synced repository
- **THEN** it SHALL receive a summary of the tree, primary languages, important files, and (for code modes) key modules/symbols

### Requirement: Engineering-intelligence MCP tools
The MCP server SHALL expose engineering-intelligence tools, each requiring the same bearer authentication and `mnemosyne` entitlement as existing tools, and each returning structured JSON:

- `mnemosyne_get_repository_health` — a repository's health score, grade, component breakdown, and findings.
- `mnemosyne_get_delivery_metrics` — cycle/lead time, PR size distribution, throughput, merge rate.
- `mnemosyne_get_backlog_metrics` — open/stale backlog, ratios, oldest-open age.
- `mnemosyne_get_review_bottlenecks` — slow/absent-review PRs and reviewer-load concentration.
- `mnemosyne_get_maintenance_risk` — risk level with reasons.
- `mnemosyne_get_portfolio_overview` — cross-repo leaderboard, most-active, abandoned, bug-heavy.
- `mnemosyne_compare_repositories` — aligned comparison of chosen repositories.
- `mnemosyne_generate_onboarding_summary` — newcomer brief for a repository.

When the underlying data is absent (repository not synced, or its mode does not capture the required inputs), the tool SHALL return a structured insufficient-data result, not an error.

#### Scenario: Health tool returns a scored result
- **GIVEN** an authenticated caller with the `mnemosyne` entitlement
- **AND** a synced repository
- **WHEN** `mnemosyne_get_repository_health` is called for it
- **THEN** the tool SHALL return the overall score, grade, component breakdown, and findings

#### Scenario: Portfolio tool aggregates across repositories
- **WHEN** `mnemosyne_get_portfolio_overview` is called
- **THEN** the tool SHALL return the health leaderboard and the most-active, abandoned, and bug-heavy groupings

#### Scenario: Insufficient data is structured, not an error
- **GIVEN** a repository that has not been synced
- **WHEN** `mnemosyne_get_repository_health` is called for it
- **THEN** the tool SHALL return an insufficient-data result rather than raising an error

#### Scenario: Unauthenticated call rejected
- **GIVEN** a caller without a valid bearer token
- **WHEN** any engineering-intelligence tool is called
- **THEN** the call SHALL be rejected as unauthenticated

### Requirement: Delivery-intelligence MCP tools
The MCP server SHALL expose PM/PO delivery tools, each requiring the same bearer authentication
and `mnemosyne` entitlement as existing tools and returning structured JSON:

- `mnemosyne_get_flow_metrics` — cycle/lead-time percentiles, WIP, aging buckets, untriaged backlog.
- `mnemosyne_get_throughput_trend` — throughput and net-flow over the time-series.
- `mnemosyne_get_backlog_forecast` — projected backlog-clear date (or reason there is none).
- `mnemosyne_get_work_mix` — feature/bug/tech-debt/docs distribution and bug ratio.
- `mnemosyne_get_quality_signals` — bug ratio, reopened-issue rate, first-response percentiles.
- `mnemosyne_get_milestone_progress` — per-milestone burn-up and projected completion.
- `mnemosyne_get_team_load` — load distribution and bus-factor risk (no per-person ranking).
- `mnemosyne_get_delivery_scorecard` — portfolio-level delivery scorecard.

When the underlying data or history is absent, the tool SHALL return a structured
insufficient-data result, not an error.

#### Scenario: Flow tool returns percentiles
- **GIVEN** an authenticated caller with the `mnemosyne` entitlement and a repository with closed work
- **WHEN** `mnemosyne_get_flow_metrics` is called
- **THEN** the tool SHALL return the cycle/lead percentiles, WIP, and aging buckets

#### Scenario: Forecast with insufficient history
- **GIVEN** a repository with too few snapshots
- **WHEN** `mnemosyne_get_backlog_forecast` is called
- **THEN** the tool SHALL return a structured insufficient-history result, not an error

#### Scenario: Unauthenticated call rejected
- **GIVEN** a caller without a valid bearer token
- **WHEN** any delivery tool is called
- **THEN** the call SHALL be rejected as unauthenticated

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

### Requirement: Intelligence tools reject un-indexed repositories
The MCP engineering-intelligence and delivery tools SHALL reject a repository that is not indexed
(disabled), returning a structured not-indexed result rather than its stale metrics.

#### Scenario: Health tool on a disabled repository
- **GIVEN** a disabled repository
- **WHEN** `mnemosyne_get_repository_health` is called for it
- **THEN** the tool SHALL return a not-indexed error result

### Requirement: MCP OAuth connector flow

The MCP server SHALL support the MCP OAuth 2.1 authorization flow so that clients
which self-register (claude.ai, Claude Desktop) can connect with no manually
supplied token. The server SHALL act as an OAuth authorization server **from the
client's perspective** by serving protected-resource metadata, authorization-server
metadata, a dynamic-client-registration endpoint, and authorization + token
endpoints, and SHALL bridge the authorization to CyberdyneAuth using a single
pre-registered upstream client. The authorization-code exchange SHALL use PKCE
(S256). The resulting user token SHALL authorize tool calls through the existing
`mnemosyne` entitlement check (no audience binding required). The flow SHALL be
feature-flagged and disabled by default.

#### Scenario: Protected-resource metadata advertised
- **WHEN** a client requests `/.well-known/oauth-protected-resource` from the MCP server with OAuth enabled
- **THEN** the server SHALL return metadata identifying the authorization server and the required audience

#### Scenario: Dynamic client registration
- **WHEN** a DCR-only client posts a registration request to the server's registration endpoint
- **THEN** the server SHALL issue a client registration (client id + stored redirect URIs) without requiring the client to register with CyberdyneAuth directly

#### Scenario: Authorization-code flow bridged to CyberdyneAuth
- **WHEN** a registered client begins an authorization-code + PKCE flow
- **THEN** the server SHALL forward the authorization to CyberdyneAuth, complete the code exchange with the upstream client credentials, and return the resulting user access (and refresh) token to the client

#### Scenario: Token from the flow authorizes tool calls
- **WHEN** a client calls a tool with a bearer token obtained through the OAuth flow
- **THEN** the server SHALL validate it via the existing auth path and authorize the call only if the caller holds the `mnemosyne` entitlement

#### Scenario: Authenticated user lacking entitlement
- **WHEN** a user completes the OAuth login but does not hold the `mnemosyne` entitlement
- **THEN** tool calls SHALL be rejected with a missing-entitlement error

#### Scenario: Existing credentials still accepted
- **WHEN** a client connects with a Mnemosyne API key (`mnem_…`) or a directly supplied CyberdyneAuth bearer token
- **THEN** the server SHALL authenticate it as before, independent of the OAuth flow

#### Scenario: OAuth disabled
- **WHEN** the OAuth feature flag is off
- **THEN** the server SHALL not serve OAuth metadata endpoints and SHALL continue to accept API-key and bearer credentials

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

