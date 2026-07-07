# mcp-interface — FastMCP server for agents

## ADDED Requirements

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
