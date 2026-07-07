# web-ui — engineering-intelligence dashboard

## ADDED Requirements

### Requirement: Intelligence dashboard
The web UI SHALL provide an Intelligence dashboard route presenting the portfolio overview: a health-ranked repository leaderboard (score + grade), the most-active repositories, abandoned repositories, and bug-heavy repositories. Repositories without metrics SHALL be shown with an insufficient-data indicator. All list renders SHALL use stable keys.

#### Scenario: Portfolio dashboard loads
- **GIVEN** an authenticated user with the `mnemosyne` entitlement
- **WHEN** they open the Intelligence dashboard
- **THEN** the health leaderboard and the most-active, abandoned, and bug-heavy groupings SHALL be displayed

#### Scenario: Repository lacking metrics
- **GIVEN** an enabled repository that has not been synced
- **WHEN** the dashboard renders
- **THEN** that repository SHALL show an insufficient-data indicator rather than a fabricated score

### Requirement: Repository health panel
The web UI SHALL present, on the repository detail page, a health panel showing the repository's overall score, letter grade, per-component breakdown, and findings.

#### Scenario: Health panel on repository detail
- **GIVEN** a synced repository
- **WHEN** the user opens its detail page
- **THEN** the health panel SHALL show the overall score, grade, component sub-scores, and findings

#### Scenario: Component with unknown inputs
- **GIVEN** a repository whose indexing mode does not capture a file tree
- **WHEN** the health panel renders
- **THEN** the testing/CI component SHALL be shown as not-applicable rather than as a zero score
