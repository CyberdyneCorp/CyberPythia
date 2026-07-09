# rest-api Specification

## ADDED Requirements

### Requirement: Cross-repository and capability REST endpoints

The REST API SHALL mirror the cross-repository and capability tools for entitled
callers: `GET /api/v1/intelligence/search` (query, `kind` of docs|code|issues,
optional `organization`, `limit`), `GET /api/v1/intelligence/stale-issues` and
`/stale-prs`, `GET /api/v1/intelligence/recent-activity`, and
`GET /api/v1/repos/find`. The search endpoint SHALL reject an invalid `kind` with a
422. `GET /api/v1/intelligence/portfolio` and `/delivery-scorecard` SHALL accept an
optional `organization` query parameter, and `GET
/api/v1/intelligence/organizations/{org}/intelligence` and
`/organizations/{org}/capabilities` SHALL return the organization rollup and
capability union. `GET /api/v1/repos/{id}/capabilities` SHALL return the repository
capability overview and `POST /api/v1/repos/{id}/feature-document` SHALL return a
grounded Markdown features document.

#### Scenario: Search endpoint
- **WHEN** an entitled caller GETs `/api/v1/intelligence/search?query=…&kind=docs`
- **THEN** the response SHALL contain ranked results across indexed repositories, each with its repository identity

#### Scenario: Invalid search kind rejected
- **WHEN** the `kind` parameter is not docs, code, or issues
- **THEN** the API SHALL respond 422

#### Scenario: Organization-scoped portfolio
- **WHEN** an entitled caller GETs `/api/v1/intelligence/portfolio?organization=…`
- **THEN** the response SHALL include only that organization's repositories

#### Scenario: Repository capabilities and feature document
- **WHEN** an entitled caller GETs `/api/v1/repos/{id}/capabilities` or POSTs `/api/v1/repos/{id}/feature-document`
- **THEN** the API SHALL return the capability overview or a grounded Markdown features document respectively
