# rest-api Specification

## ADDED Requirements

### Requirement: Organization digest endpoint

The REST API SHALL expose `GET /api/v1/intelligence/organizations/{org}/digest`
returning the organization's attention digest (readiness regressions, stale
issues/PRs, at-risk milestones, and a summary), for entitled callers.

#### Scenario: Digest endpoint
- **WHEN** an entitled caller GETs `/api/v1/intelligence/organizations/{org}/digest`
- **THEN** the response SHALL contain the digest sections and a summary line
