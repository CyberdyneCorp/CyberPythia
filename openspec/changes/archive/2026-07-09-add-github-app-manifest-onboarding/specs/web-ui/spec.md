# web-ui Specification

## ADDED Requirements

### Requirement: One-click GitHub App creation

The Connections screen SHALL offer admins a "Create GitHub App" action for an
organization that hands off to GitHub's App-creation page (auto-submitting the
manifest returned by the backend). After GitHub round-trips through the manifest and
setup callbacks, the admin SHALL land back on the Connections screen with the new
`github_app` connection shown as active. The manual App-connect form SHALL remain as
an alternative.

#### Scenario: Start App creation from the dashboard
- **WHEN** an admin clicks "Create GitHub App" for an organization
- **THEN** the browser SHALL be handed off to GitHub's App-creation page pre-filled from the manifest

#### Scenario: Return after install
- **WHEN** the manifest + install round-trip completes
- **THEN** the admin SHALL be returned to the Connections screen showing the new App connection as active
