# rest-api — organization management endpoints

## ADDED Requirements

### Requirement: Organization list and toggle endpoints
The REST API SHALL expose admin-only endpoints to manage organization sync scope:

- `GET /api/v1/github/organizations` — list organizations with `sync_enabled` and repository
  counts (total and enabled).
- `PATCH /api/v1/github/organizations/{login}` — set an organization's `sync_enabled` flag.

Both SHALL require admin authorization and reject non-admin callers.

#### Scenario: Admin lists organizations
- **GIVEN** an admin caller and discovered organizations
- **WHEN** `GET /api/v1/github/organizations` is called
- **THEN** the response SHALL list each organization with its sync flag and repo counts

#### Scenario: Admin disables an organization
- **GIVEN** an admin caller
- **WHEN** `PATCH /api/v1/github/organizations/{login}` sets sync disabled
- **THEN** the organization SHALL be persisted as sync-disabled

#### Scenario: Non-admin rejected
- **GIVEN** a caller without admin authorization
- **WHEN** either endpoint is called
- **THEN** the API SHALL reject the request
