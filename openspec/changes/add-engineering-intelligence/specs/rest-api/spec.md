# rest-api — engineering-intelligence endpoints

## ADDED Requirements

### Requirement: Engineering-intelligence REST endpoints
The REST API SHALL expose engineering-intelligence endpoints under `/api/v1/intelligence`, each requiring the same bearer authentication and `mnemosyne` entitlement as existing admin/query endpoints:

- `GET /api/v1/intelligence/portfolio` — portfolio overview (leaderboard, most-active, abandoned, bug-heavy).
- `GET /api/v1/intelligence/repositories/{id}/health` — repository health score, grade, components, findings.
- `GET /api/v1/intelligence/repositories/{id}/delivery` — delivery metrics.
- `GET /api/v1/intelligence/repositories/{id}/backlog` — backlog metrics.
- `GET /api/v1/intelligence/repositories/{id}/review-bottlenecks` — review-bottleneck analysis.
- `GET /api/v1/intelligence/repositories/{id}/maintenance-risk` — maintenance-risk assessment.
- `GET /api/v1/intelligence/repositories/{id}/onboarding` — onboarding summary.
- `POST /api/v1/intelligence/compare` — compare a set of repository ids.

Endpoints SHALL return a well-formed response with insufficient-data markers when metrics are absent, and SHALL return the standard not-found error for an unknown repository id.

#### Scenario: Fetch repository health over REST
- **GIVEN** an authenticated, entitled caller and a synced repository
- **WHEN** `GET /api/v1/intelligence/repositories/{id}/health` is called
- **THEN** the response SHALL contain the overall score, grade, component breakdown, and findings

#### Scenario: Portfolio endpoint
- **WHEN** `GET /api/v1/intelligence/portfolio` is called by an entitled caller
- **THEN** the response SHALL contain the leaderboard and the most-active, abandoned, and bug-heavy groupings

#### Scenario: Unknown repository
- **WHEN** an intelligence endpoint is called with an id that does not exist
- **THEN** the API SHALL return a not-found error

#### Scenario: Missing entitlement rejected
- **GIVEN** a caller authenticated without the `mnemosyne` entitlement
- **WHEN** any intelligence endpoint is called
- **THEN** the API SHALL reject the request as forbidden
