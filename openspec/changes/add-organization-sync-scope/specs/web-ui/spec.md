# web-ui — organizations panel

## ADDED Requirements

### Requirement: Organizations sync panel
The web UI SHALL present, on the GitHub Connection page, an Organizations panel listing each
discovered organization with its repository counts (total / enabled) and a control to enable or
disable sync for that organization. Toggling SHALL persist immediately.

#### Scenario: Admin disables an organization from the UI
- **GIVEN** the Organizations panel lists several organizations
- **WHEN** the admin turns off sync for one organization
- **THEN** that organization SHALL be persisted as sync-disabled and reflected in the panel
