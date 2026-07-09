# github-connection Specification

## ADDED Requirements

### Requirement: GitHub App manifest onboarding

The system SHALL support creating and connecting a GitHub App via GitHub's App
Manifest flow, initiated by an admin from the dashboard. The system SHALL generate a
manifest pre-configured with read-only Contents/Issues/Pull-requests/Metadata
permissions, the webhook event set, and the Mnemosyne webhook, redirect, and setup
URLs. After GitHub creates the App, the system SHALL convert the returned one-time
code into the App's credentials (App ID, private key, webhook secret) server-side and
persist them as a `github_app` connection, encrypted at rest and never returned by any
API. The connection SHALL be `pending_installation` until an installation ID is
captured, at which point the system SHALL validate it by minting an installation token
and mark it active. Discovery and sync SHALL ignore `pending_installation` connections.

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
