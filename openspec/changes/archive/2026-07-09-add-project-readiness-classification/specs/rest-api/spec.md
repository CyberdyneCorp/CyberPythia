# rest-api Specification

## ADDED Requirements

### Requirement: Readiness endpoints

The REST API SHALL expose `GET /api/v1/repos/{id}/readiness` (a repository's gate +
per-check breakdown) and `GET /api/v1/intelligence/organizations/{org}/readiness` (the
organization gate distribution + per-repository gate and gaps), for entitled callers.

#### Scenario: Repository readiness endpoint
- **WHEN** an entitled caller GETs `/api/v1/repos/{id}/readiness`
- **THEN** the response SHALL contain the gate and the met/missing/unknown checks

#### Scenario: Organization readiness endpoint
- **WHEN** an entitled caller GETs `/api/v1/intelligence/organizations/{org}/readiness`
- **THEN** the response SHALL contain the per-gate distribution and per-repository gates
