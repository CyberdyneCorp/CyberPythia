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

