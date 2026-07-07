# github-app — App authentication & installation management

## ADDED Requirements

### Requirement: App installation tokens
The system SHALL authenticate to GitHub as a GitHub App by minting an RS256 app JWT (signed with the App private key, `iss` = app id, short expiry) and exchanging it for a short-lived installation access token via the GitHub App installations API. Installation tokens SHALL be cached in memory until shortly before expiry and re-minted on demand; they SHALL NOT be persisted. The App private key SHALL be stored encrypted at rest and never returned by any API.

#### Scenario: Mint an installation token
- **WHEN** a sync needs to call GitHub for an App-backed connection
- **THEN** the system SHALL mint (or reuse a cached) installation access token and use it as the bearer credential

#### Scenario: Token expiry
- **WHEN** a cached installation token is within the refresh window of its expiry
- **THEN** the system SHALL mint a fresh token before making the call

#### Scenario: Invalid App credentials
- **WHEN** the App id or private key is rejected by GitHub
- **THEN** the connection SHALL be marked broken and the failure surfaced, and no token SHALL be returned

### Requirement: Register a GitHub App installation
The system SHALL allow an admin to register a GitHub App installation as a connection of kind `github_app`, supplying the app id, installation id, App private key, and webhook secret. On registration the system SHALL validate the credentials by minting an installation token and SHALL persist the private key and webhook secret encrypted.

#### Scenario: Valid installation registered
- **WHEN** an admin submits valid App credentials for an installation
- **THEN** the system SHALL verify them against GitHub, persist an encrypted `github_app` connection, and report the resolved owner

#### Scenario: Invalid installation rejected
- **WHEN** the credentials fail to mint an installation token
- **THEN** the registration SHALL be rejected and nothing SHALL be persisted

### Requirement: Installation repository discovery
The system SHALL list the repositories an installation grants (the installation-repositories API) and reconcile them into the repository table, preserving each repository's existing selection and indexing mode.

#### Scenario: Discover installation repositories
- **WHEN** an admin runs discovery on a `github_app` connection
- **THEN** the repositories the installation can access SHALL be listed with metadata, without indexing content, and prior selection state SHALL be preserved
