# web-ui — organization filter on the dashboard

## ADDED Requirements

### Requirement: Organization filter on the Repositories dashboard
The Repositories dashboard SHALL provide an organization filter that restricts the listed
repositories to a chosen organization, combining with the existing text filter. The available
organizations SHALL be derived from the loaded repositories.

#### Scenario: Filter the dashboard by organization
- **GIVEN** the dashboard lists repositories from several organizations
- **WHEN** the user selects one organization in the filter
- **THEN** only that organization's repositories SHALL be shown

#### Scenario: Clearing the organization filter
- **WHEN** the user clears the organization filter
- **THEN** repositories from all organizations SHALL be shown again
