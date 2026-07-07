# rest-api — PM/PO delivery endpoints

## ADDED Requirements

### Requirement: Delivery-intelligence REST endpoints
The REST API SHALL expose PM/PO delivery endpoints, each requiring the same bearer
authentication and `mnemosyne` entitlement as existing intelligence endpoints:

- `GET /api/v1/intelligence/repositories/{id}/flow` — percentiles, WIP, aging, untriaged.
- `GET /api/v1/intelligence/repositories/{id}/throughput` — throughput and net-flow trend.
- `GET /api/v1/intelligence/repositories/{id}/forecast` — backlog forecast.
- `GET /api/v1/intelligence/repositories/{id}/work-mix` — work-class distribution and bug ratio.
- `GET /api/v1/intelligence/repositories/{id}/quality` — bug ratio, reopen rate, first-response.
- `GET /api/v1/intelligence/repositories/{id}/milestones` — per-milestone progress and projection.
- `GET /api/v1/intelligence/repositories/{id}/team-load` — load distribution and bus factor.
- `GET /api/v1/intelligence/delivery-scorecard` — portfolio delivery scorecard.

Endpoints SHALL return insufficient-data markers when metrics or history are absent and SHALL
return the standard not-found error for an unknown repository id.

#### Scenario: Fetch flow metrics over REST
- **GIVEN** an authenticated, entitled caller and a repository with closed work
- **WHEN** `GET /api/v1/intelligence/repositories/{id}/flow` is called
- **THEN** the response SHALL contain cycle/lead percentiles, WIP, and aging buckets

#### Scenario: Milestones endpoint flags at-risk
- **GIVEN** a repository with a milestone projected to miss its due date
- **WHEN** `GET /api/v1/intelligence/repositories/{id}/milestones` is called
- **THEN** the response SHALL mark that milestone at-risk

#### Scenario: Unknown repository
- **WHEN** a delivery endpoint is called with an id that does not exist
- **THEN** the API SHALL return a not-found error

#### Scenario: Missing entitlement rejected
- **GIVEN** a caller authenticated without the `mnemosyne` entitlement
- **WHEN** any delivery endpoint is called
- **THEN** the API SHALL reject the request as forbidden
