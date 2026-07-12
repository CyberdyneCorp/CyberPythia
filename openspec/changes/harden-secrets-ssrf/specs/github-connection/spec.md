# github-connection Specification

## MODIFIED Requirements

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
returned by any API. The system SHALL refuse to persist a connection whose webhook
secret is empty or blank (CWE-347). Before redirecting the admin to install the App,
the system SHALL verify the GitHub-supplied App `html_url` is same-origin with the
configured `github_web_base_url`; a value that is not GitHub-hosted SHALL be rejected
and SHALL NOT be used as a redirect target (CWE-601). The connection SHALL be
`pending_installation` until an installation ID is captured, at which point the system
SHALL validate it by minting an installation token and mark it active. Discovery and
sync SHALL ignore `pending_installation` connections.

#### Scenario: Manifest conversion yields credentials
- **WHEN** GitHub redirects back after App creation with a one-time code
- **THEN** the system SHALL exchange it for the App ID, private key, and webhook secret, persist them encrypted, and record a `pending_installation` connection

#### Scenario: Empty webhook secret refused
- **WHEN** manifest conversion or manual App-connect supplies an empty or blank webhook secret
- **THEN** the system SHALL reject the request and SHALL NOT persist the connection

#### Scenario: Non-GitHub install URL rejected
- **WHEN** the converted credentials carry an `html_url` that is not same-origin with `github_web_base_url`
- **THEN** the system SHALL reject it and fall back to the dashboard error redirect rather than redirecting off-site

#### Scenario: Installation finalizes the connection
- **WHEN** GitHub redirects to the setup URL after the App is installed, carrying an installation ID
- **THEN** the system SHALL attach the installation ID, mint an installation token to validate, and mark the connection active

#### Scenario: State integrity on the round-trip
- **WHEN** a manifest or setup callback arrives without a valid CSRF `state`
- **THEN** the system SHALL reject it and not create or modify a connection

#### Scenario: Manual App-connect remains available
- **WHEN** an admin uses the manual App-connect form with App ID / installation ID / PEM / secret
- **THEN** the system SHALL register the connection as before, independent of the manifest flow
