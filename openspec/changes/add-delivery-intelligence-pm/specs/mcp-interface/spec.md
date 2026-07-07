# mcp-interface — PM/PO delivery tools

## ADDED Requirements

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
