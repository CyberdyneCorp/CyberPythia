# github-connection — GitHub read credential management

## ADDED Requirements

### Requirement: Connect a GitHub credential
The system SHALL allow an admin to register a read-only GitHub credential (fine-grained PAT for this change) scoped to a user account or organization. On registration the system SHALL validate the credential against the GitHub API and record the granted permissions and the owner (user or org) it resolves to.

#### Scenario: Valid PAT registered
- **WHEN** an admin submits a PAT with Contents, Issues, Pull requests, and Metadata read permissions
- **THEN** the system SHALL verify it with a GitHub API call, persist it encrypted, and return the resolved owner and detected permissions

#### Scenario: PAT lacking required permissions
- **WHEN** an admin submits a PAT missing a required read permission
- **THEN** the system SHALL reject the registration and report which permissions are missing

#### Scenario: Invalid or revoked PAT
- **WHEN** an admin submits a credential GitHub rejects
- **THEN** the system SHALL respond with a validation error and SHALL NOT persist the credential

### Requirement: Credential encryption at rest
The system SHALL encrypt GitHub credentials with an application-level symmetric key (`TOKEN_ENCRYPTION_KEY`) before persistence. Plaintext credentials SHALL never be written to the database, logs, object storage, or error messages, and SHALL never be returned by any API after registration.

#### Scenario: Reading a stored connection
- **WHEN** any API returns a GitHub connection resource
- **THEN** the credential value SHALL be omitted or masked (last 4 characters at most)

### Requirement: Connection health check
The system SHALL provide an on-demand connection test that verifies the stored credential still authenticates and reports the remaining GitHub rate limit.

#### Scenario: Test succeeds
- **WHEN** an admin triggers a connection test on a healthy credential
- **THEN** the system SHALL report success, granted scopes, and rate-limit status

#### Scenario: Credential revoked upstream
- **WHEN** the test fails with 401 from GitHub
- **THEN** the system SHALL mark the connection as broken and surface this state on the dashboard and sync attempts

### Requirement: Credential lifecycle
The system SHALL allow an admin to rotate (replace) or delete a credential. Deleting a credential SHALL NOT delete already-indexed data but SHALL disable further syncs for its repositories.

#### Scenario: Credential rotation
- **WHEN** an admin replaces a credential for an owner
- **THEN** subsequent syncs SHALL use the new credential and the old value SHALL be destroyed
