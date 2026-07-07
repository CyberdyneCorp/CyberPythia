# web-ui — GitHub App connection & webhook activity

## ADDED Requirements

### Requirement: GitHub App connection screen (admin)
The admin GitHub connection area SHALL let an admin register a GitHub App installation (app id, installation id, App private key, webhook secret), alongside the existing PAT flow, and trigger installation-repository discovery. Secret fields SHALL be masked and never re-displayed after submission.

#### Scenario: Admin registers an App installation
- **WHEN** an admin submits App installation credentials
- **THEN** the UI SHALL show validation results (resolved owner) and enable discovery, without echoing the private key or webhook secret

### Requirement: Webhook activity panel
The admin area SHALL display recent webhook deliveries (event, action, repository, outcome, time) so an admin can confirm near-real-time updates are flowing.

#### Scenario: View recent deliveries
- **WHEN** an admin opens the webhook activity panel after events have arrived
- **THEN** recent deliveries SHALL be listed with their event type, target repository, and outcome
