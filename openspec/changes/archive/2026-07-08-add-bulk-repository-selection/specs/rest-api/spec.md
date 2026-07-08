# rest-api — bulk repository selection

## ADDED Requirements

### Requirement: Bulk repository selection endpoint
The REST API SHALL provide an admin-only endpoint to set the enabled state (and optionally the
indexing mode) for a list of repositories in a single request, returning the number of
repositories updated. Repository ids that do not exist SHALL be ignored rather than failing the
request.

#### Scenario: Bulk enable a set of repositories
- **GIVEN** an admin caller and a list of repository ids
- **WHEN** `POST /api/v1/repos/selection` is called with `enabled: true` and a mode
- **THEN** each listed repository SHALL be enabled in that mode and the updated count returned

#### Scenario: Bulk disable
- **WHEN** the endpoint is called with `enabled: false` for a list of repositories
- **THEN** each listed repository SHALL be disabled

#### Scenario: Non-admin rejected
- **GIVEN** a caller without admin authorization
- **WHEN** the endpoint is called
- **THEN** the API SHALL reject the request
