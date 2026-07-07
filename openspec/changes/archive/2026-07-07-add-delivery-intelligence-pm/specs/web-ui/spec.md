# web-ui — delivery dashboard

## ADDED Requirements

### Requirement: Delivery dashboard view
The web UI SHALL provide a Delivery view on the Intelligence dashboard presenting, across the
portfolio, throughput and net-flow trends, backlog forecasts, work-mix distribution, and
at-risk milestones. Charts SHALL be self-contained (no external chart dependency). Repositories
or metrics lacking data SHALL show an insufficient-data indicator. All list and chart renders
SHALL use stable keys.

#### Scenario: Delivery view loads
- **GIVEN** an authenticated user with the `mnemosyne` entitlement
- **WHEN** they open the Delivery view
- **THEN** throughput/net-flow, backlog forecast, work-mix, and at-risk milestones SHALL be displayed

#### Scenario: History still collecting
- **GIVEN** a repository without enough snapshots for a trend
- **WHEN** the Delivery view renders it
- **THEN** it SHALL show a "collecting history" indicator instead of a fabricated trend

### Requirement: Repository delivery panel
The web UI SHALL present, on the repository detail page, a delivery panel showing cycle/lead
percentiles, WIP and aging, work-mix, and milestone progress for that repository.

#### Scenario: Delivery panel on repository detail
- **GIVEN** a synced repository with closed work
- **WHEN** the user opens its detail page
- **THEN** the delivery panel SHALL show percentiles, WIP/aging, work-mix, and milestone progress

#### Scenario: Metric with no data
- **GIVEN** a repository with no merged PRs
- **WHEN** the delivery panel renders
- **THEN** the affected metric SHALL be shown as insufficient data rather than zero
