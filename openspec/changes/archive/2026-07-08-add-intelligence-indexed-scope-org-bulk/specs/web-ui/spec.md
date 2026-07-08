# web-ui — per-organization index controls

## ADDED Requirements

### Requirement: Index-all / Un-index-all per organization
The Organizations panel SHALL provide, per organization, controls to index (enable) or un-index
(disable) all of that organization's repositories at once, with a mode selection for indexing. The
organization's repository counts SHALL update after the action.

#### Scenario: Un-index an organization from the panel
- **GIVEN** the Organizations panel lists an organization with indexed repositories
- **WHEN** the admin chooses Un-index all for it
- **THEN** all of that organization's repositories SHALL become disabled and the counts SHALL reflect it
