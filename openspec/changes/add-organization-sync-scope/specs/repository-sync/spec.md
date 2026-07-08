# repository-sync — organization-scoped scheduled runs

## ADDED Requirements

### Requirement: Scheduled runs skip sync-disabled organizations
The scheduled discovery and sync SHALL skip any repository whose owning organization is
sync-disabled. A repository whose organization is sync-enabled, or whose organization is not yet
recorded, SHALL be unaffected (fail-open). The scheduled sync SHALL count repositories skipped for
this reason in its run summary, and the scheduled auto-enable SHALL NOT enable a newly-discovered
repository in a sync-disabled organization.

#### Scenario: Repositories in a disabled organization are not synced
- **GIVEN** an organization whose sync is disabled
- **WHEN** the scheduled sync runs
- **THEN** enabled repositories in that organization SHALL NOT be enqueued

#### Scenario: Repositories in an enabled organization still sync
- **GIVEN** an organization whose sync is enabled
- **WHEN** the scheduled sync runs
- **THEN** its enabled repositories SHALL be enqueued as before

#### Scenario: Unknown organization is fail-open
- **GIVEN** a repository whose organization has no record yet
- **WHEN** the scheduled sync runs
- **THEN** the repository SHALL be treated as in scope and synced

#### Scenario: Auto-enable respects organization scope
- **GIVEN** a newly-discovered non-archived repository in a sync-disabled organization
- **WHEN** scheduled discovery runs
- **THEN** that repository SHALL NOT be auto-enabled
