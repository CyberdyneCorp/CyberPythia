# github-connection Specification

## Purpose
TBD - created by archiving change add-github-context-memory-core. Update Purpose after archive.
## Requirements
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
The system SHALL allow an admin to rotate (replace) or delete a credential.
Deleting a credential SHALL cascade-delete the repositories indexed under it and
their derived data, but SHALL do so **safely**: the number of repositories under
a connection SHALL be reported before deletion, the deletion SHALL run
asynchronously in the background worker (the connection is marked `deleting` and
removed on completion) so a large cascade cannot block or time out the request,
and callers SHALL be able to surface deletion failures.

#### Scenario: Credential rotation
- **WHEN** an admin replaces a credential for an owner
- **THEN** subsequent syncs SHALL use the new credential and the old value SHALL be destroyed

#### Scenario: Deletion is deferred to the worker
- **WHEN** an admin deletes a connection
- **THEN** the connection SHALL be marked `deleting` and a background job SHALL be enqueued to cascade-delete it and its repositories
- **AND** the connection SHALL be removed once the job completes

#### Scenario: Impact is known before deletion
- **WHEN** an admin lists connections
- **THEN** each connection SHALL report how many repositories are indexed under it

### Requirement: Connection credential kinds
A GitHub connection SHALL have a kind of `pat` or `github_app`. A `pat` connection stores an encrypted fine-grained token (unchanged). A `github_app` connection stores the app id, installation id, encrypted App private key, and encrypted webhook secret. Both kinds SHALL resolve to a usable GitHub credential for discovery and sync, so downstream capabilities are credential-agnostic. No connection SHALL ever return its secret material after registration.

#### Scenario: PAT connection unchanged
- **WHEN** a `pat` connection is used for sync
- **THEN** it SHALL behave exactly as before this change

#### Scenario: App connection provides a token
- **WHEN** a `github_app` connection is used for sync
- **THEN** the system SHALL mint an installation token and proceed identically to a PAT connection

#### Scenario: Secrets never exposed
- **WHEN** any API returns a connection resource
- **THEN** the private key, webhook secret, and any token SHALL be omitted or masked

### Requirement: Track organizations with a sync toggle
The system SHALL track each GitHub organization it discovers (by login) and associate a
`sync_enabled` flag with it. When repositories are discovered, the system SHALL upsert an
organization record for every distinct repository owner, defaulting a newly-seen organization's
`sync_enabled` flag to a configured default and preserving the flag of an already-known
organization. An admin SHALL be able to enable or disable sync for an organization.

#### Scenario: Discovery records organizations
- **WHEN** repositories are discovered across several organizations
- **THEN** an organization record SHALL exist for each distinct owner with a sync-enabled flag

#### Scenario: Existing organization flag is preserved
- **GIVEN** an organization that an admin has disabled
- **WHEN** discovery runs again and sees it
- **THEN** its `sync_enabled` flag SHALL remain disabled

#### Scenario: Admin toggles an organization
- **WHEN** an admin disables sync for an organization
- **THEN** the organization's `sync_enabled` flag SHALL be set to false

### Requirement: GitHub App manifest onboarding

The system SHALL support creating and connecting a GitHub App via GitHub's App
Manifest flow, initiated by an admin from the dashboard. The system SHALL generate a
manifest pre-configured with read-only Contents/Issues/Pull-requests/Metadata
permissions plus read-only security-alert permissions (Dependabot
`vulnerability_alerts` and code-scanning `security_events`, used for vulnerability
and readiness intelligence), the webhook event set, and the Mnemosyne webhook,
redirect, and setup URLs. After GitHub creates the App, the system SHALL convert the
returned one-time code into the App's credentials (App ID, private key, webhook secret)
server-side and persist them as a `github_app` connection, encrypted at rest and never
returned by any API. The connection SHALL be `pending_installation` until an
installation ID is captured, at which point the system SHALL validate it by minting an
installation token and mark it active. Discovery and sync SHALL ignore
`pending_installation` connections.

#### Scenario: Manifest conversion yields credentials
- **WHEN** GitHub redirects back after App creation with a one-time code
- **THEN** the system SHALL exchange it for the App ID, private key, and webhook secret, persist them encrypted, and record a `pending_installation` connection

#### Scenario: Installation finalizes the connection
- **WHEN** GitHub redirects to the setup URL after the App is installed, carrying an installation ID
- **THEN** the system SHALL attach the installation ID, mint an installation token to validate, and mark the connection active

#### Scenario: State integrity on the round-trip
- **WHEN** a manifest or setup callback arrives without a valid CSRF `state`
- **THEN** the system SHALL reject it and not create or modify a connection

#### Scenario: Manual App-connect remains available
- **WHEN** an admin uses the manual App-connect form with App ID / installation ID / PEM / secret
- **THEN** the system SHALL register the connection as before, independent of the manifest flow

