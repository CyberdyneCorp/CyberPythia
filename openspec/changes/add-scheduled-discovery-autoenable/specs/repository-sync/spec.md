# repository-sync — scheduled discovery & auto-enable

## ADDED Requirements

### Requirement: Scheduled discovery with auto-enable of new repositories
The system SHALL, as part of the daily scheduled job, re-discover the repositories each
connection can access and auto-enable repositories that are **newly discovered** — a repository
whose GitHub id was not present before the run — provided the repository is not archived, using a
configured indexing mode. The system SHALL NOT change the enabled state of any repository that
already existed, so a repository an admin has disabled SHALL remain disabled. Discovery and
auto-enable SHALL run before the daily full sync so a new repository is discovered, enabled, and
synced in the same run. The behaviour SHALL be configurable and disableable.

#### Scenario: A newly-created repository is auto-enabled and synced
- **GIVEN** a repository that appears in discovery for the first time and is not archived
- **WHEN** the scheduled job runs
- **THEN** that repository SHALL be enabled in the configured mode
- **AND** it SHALL be included in the same run's full sync

#### Scenario: Manually disabled repositories are not re-enabled
- **GIVEN** a repository that already existed and was disabled by an admin
- **WHEN** the scheduled discovery runs and sees it again
- **THEN** its enabled state SHALL be left unchanged (it SHALL remain disabled)

#### Scenario: Archived repositories are skipped
- **GIVEN** a newly-discovered repository that is archived
- **WHEN** auto-enable runs
- **THEN** that repository SHALL NOT be enabled

#### Scenario: Auto-enable disabled by configuration
- **GIVEN** auto-enable is turned off by configuration
- **WHEN** the scheduled discovery runs
- **THEN** no repository SHALL be enabled, even if newly discovered
