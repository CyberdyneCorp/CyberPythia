# rest-api — organization-scoped bulk selection

## ADDED Requirements

### Requirement: Bulk selection by organization
The bulk repository-selection endpoint SHALL accept an `organization` as an alternative to an
explicit list of repository ids, applying the enable/disable (and optional mode) to every
repository in that organization in a single request, and returning the number updated. The request
SHALL require either a repository-id list or an organization.

#### Scenario: Un-index a whole organization
- **GIVEN** an admin caller and an organization with several repositories
- **WHEN** `POST /api/v1/repos/selection` is called with that `organization` and `enabled: false`
- **THEN** every repository in that organization SHALL be disabled and the count returned

#### Scenario: Index a whole organization in a mode
- **WHEN** the endpoint is called with an `organization`, `enabled: true`, and a mode
- **THEN** every repository in that organization SHALL be enabled in that mode

#### Scenario: Neither ids nor organization
- **WHEN** the endpoint is called with neither repository ids nor an organization
- **THEN** the request SHALL be rejected as invalid
