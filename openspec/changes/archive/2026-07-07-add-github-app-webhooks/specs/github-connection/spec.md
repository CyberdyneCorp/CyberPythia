# github-connection — GitHub App credential kind

## ADDED Requirements

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
