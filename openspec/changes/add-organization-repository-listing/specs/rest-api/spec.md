# rest-api — organization repository filter

## ADDED Requirements

### Requirement: Filter repositories by organization
The repositories list endpoint SHALL accept an optional `organization` parameter that filters the
result to repositories whose owner matches the value (case-insensitive). The filter SHALL combine
with the existing enabled-only and pagination parameters.

#### Scenario: Filter to one organization
- **GIVEN** repositories across several organizations
- **WHEN** `GET /api/v1/repos?organization=cyberdynecorp` is called by an entitled caller
- **THEN** only repositories owned by that organization SHALL be returned

#### Scenario: No organization filter returns all
- **WHEN** the repositories list is called without an organization parameter
- **THEN** repositories across all organizations SHALL be returned as before
