# rest-api Specification

## ADDED Requirements

### Requirement: GitHub App manifest endpoints

The REST API SHALL expose an admin-only endpoint that returns the GitHub App
manifest, the GitHub App-creation POST URL for a given organization, and a signed
CSRF `state` (`GET /api/v1/github/app/manifest?organization=`). It SHALL expose the
GitHub-facing manifest callback (`GET /api/v1/github/app/manifest-callback?code=&state=`)
that converts the code to credentials and redirects to the App's install page, and the
setup callback (`GET /api/v1/github/app/setup?installation_id=&setup_action=&state=`)
that finalizes the connection and redirects to the dashboard. The callbacks are
GitHub redirects gated by the signed `state` rather than a bearer token.

#### Scenario: Manifest bootstrap
- **WHEN** an admin GETs `/api/v1/github/app/manifest?organization=<org>`
- **THEN** the response SHALL contain the manifest JSON, the org App-creation POST URL, and a signed `state`

#### Scenario: Non-admin cannot initiate
- **WHEN** a non-admin requests the manifest endpoint
- **THEN** the API SHALL respond 403

#### Scenario: Callback with invalid state
- **WHEN** either callback is called with a missing or invalid `state`
- **THEN** the API SHALL respond with an error and make no connection change
