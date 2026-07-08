# web-ui — bulk enable/disable controls

## ADDED Requirements

### Requirement: Enable-all / Disable-all on the Repositories dashboard
The Repositories dashboard SHALL provide controls to enable or disable indexing for all
repositories currently shown (after the organization and text filters are applied), with a mode
selection for the enable action. Applying a bulk action SHALL update the shown repositories in
place.

#### Scenario: Enable all filtered repositories
- **GIVEN** the dashboard is filtered to one organization
- **WHEN** the admin chooses Enable all with a mode
- **THEN** every repository in that filtered view SHALL become enabled in the chosen mode

#### Scenario: Disable all filtered repositories
- **WHEN** the admin chooses Disable all
- **THEN** every repository in the filtered view SHALL become disabled
