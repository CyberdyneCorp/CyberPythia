# rest-api Specification

## ADDED Requirements

### Requirement: OpenSpec coverage endpoint

The REST API SHALL expose `GET /api/v1/intelligence/organizations/{org}/openspec-coverage`
for entitled callers, returning the organization's indexed repositories partitioned
into `with_openspec` and `without_openspec`, the total, and a coverage ratio.

#### Scenario: Coverage for an organization
- **WHEN** an entitled caller GETs the openspec-coverage endpoint for an organization
- **THEN** the response SHALL contain the with/without repository lists, the total, and the coverage ratio
