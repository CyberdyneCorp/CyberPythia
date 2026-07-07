# mcp-interface — engineering-intelligence tools

## ADDED Requirements

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
