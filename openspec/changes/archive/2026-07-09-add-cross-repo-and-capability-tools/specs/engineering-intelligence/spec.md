# engineering-intelligence Specification

## ADDED Requirements

### Requirement: Organization-scoped rollups and capability overviews

The intelligence layer SHALL support scoping the portfolio overview and delivery
scorecard to a single organization, and SHALL compute an organization rollup
(scored/total, average and median health, grade distribution, at-risk milestone
total, throughput directions) from the scoped portfolio and scorecard. It SHALL also
compute capability overviews for a repository and for an organization, derived
(without an LLM) from indexed OpenSpec spec areas, documentation topics, and metrics
(including a bug count from bug-labelled issues).

#### Scenario: Organization rollup aggregation
- **WHEN** a rollup is requested for an organization
- **THEN** it SHALL aggregate only that organization's indexed repositories, leaving health absent when no repository has been scored

#### Scenario: Capability overview
- **WHEN** a capability overview is requested for a repository
- **THEN** it SHALL list the repository's OpenSpec spec areas, documentation topics, bug count, and issue/PR counts

#### Scenario: Absent data stays absent
- **WHEN** an organization has no scored repositories
- **THEN** the rollup's average and median health SHALL be absent rather than zero
