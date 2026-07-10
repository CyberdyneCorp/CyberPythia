# rest-api Specification

## ADDED Requirements

### Requirement: Readiness history endpoints

The REST API SHALL expose `GET /api/v1/repos/{id}/readiness-history` (a
repository's dated gate trend) and
`GET /api/v1/intelligence/organizations/{org}/readiness-regressions` (repositories
whose gate dropped, with previous/current gate and date), for entitled callers.

#### Scenario: Repository readiness history
- **WHEN** an entitled caller GETs `/api/v1/repos/{id}/readiness-history`
- **THEN** the response SHALL contain the dated gate series for that repository

#### Scenario: Organization readiness regressions
- **WHEN** an entitled caller GETs `/api/v1/intelligence/organizations/{org}/readiness-regressions`
- **THEN** the response SHALL contain repositories whose latest gate is lower than their previous gate
