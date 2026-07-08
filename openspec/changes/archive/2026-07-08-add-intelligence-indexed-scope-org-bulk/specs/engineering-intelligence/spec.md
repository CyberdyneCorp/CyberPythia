# engineering-intelligence — scoped to indexed repositories

## ADDED Requirements

### Requirement: Intelligence excludes un-indexed repositories
Engineering-intelligence and delivery-intelligence SHALL only consider repositories that are
currently indexed (enabled). Portfolio and scorecard aggregations SHALL exclude disabled
repositories, and per-repository intelligence (health, delivery, flow, backlog, forecast,
work-mix, quality, milestones, team-load, maintenance-risk, review-bottlenecks, onboarding) SHALL
treat a disabled repository as not indexed and return a not-found/not-indexed result rather than
its stale persisted metrics.

#### Scenario: Disabled repository is not in the portfolio
- **GIVEN** a repository that has been disabled
- **WHEN** the portfolio overview or delivery scorecard is requested
- **THEN** that repository SHALL NOT be included

#### Scenario: Per-repo intelligence on a disabled repository is rejected
- **GIVEN** a repository that has persisted metrics but is now disabled
- **WHEN** its per-repository intelligence is requested
- **THEN** the system SHALL respond that the repository is not indexed rather than returning its data

#### Scenario: Re-indexing restores it
- **GIVEN** a repository re-enabled for indexing
- **WHEN** intelligence is requested
- **THEN** it SHALL be considered again
