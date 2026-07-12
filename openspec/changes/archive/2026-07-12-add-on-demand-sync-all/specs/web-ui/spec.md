# web-ui Specification

## ADDED Requirements

### Requirement: Sync-now action per organization

The Connections page organization panel SHALL provide a "Sync now" action that
triggers an on-demand sync of that organization's enabled repositories and
reports how many were enqueued.

#### Scenario: Trigger org sync from the panel
- **WHEN** an admin clicks "Sync now" for an organization
- **THEN** an on-demand sync of that organization's enabled repositories SHALL be triggered
