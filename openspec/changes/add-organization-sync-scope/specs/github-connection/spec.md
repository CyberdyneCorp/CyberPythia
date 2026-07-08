# github-connection — organization sync scope

## ADDED Requirements

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
