# repository-sync — scheduled daily sync

## ADDED Requirements

### Requirement: Scheduled daily full sync
The system SHALL run a scheduled job at least once per day that enqueues a full sync for every
enabled repository, using each repository's configured indexing mode. The job SHALL skip a
repository whose sync is already pending or running (never enqueuing a duplicate), and a failure
to enqueue one repository SHALL NOT prevent the others from being enqueued. The schedule SHALL be
configurable and SHALL be disableable.

#### Scenario: Daily run enqueues all enabled repositories
- **WHEN** the scheduled sync runs
- **THEN** the system SHALL enqueue a sync for each enabled repository
- **AND** disabled repositories SHALL NOT be enqueued

#### Scenario: A repository already syncing is skipped
- **GIVEN** a repository whose sync is already pending or running
- **WHEN** the scheduled sync runs
- **THEN** that repository SHALL be skipped rather than enqueued again

#### Scenario: One repository failing does not stop the run
- **GIVEN** enqueuing one repository raises an error
- **WHEN** the scheduled sync runs
- **THEN** the remaining enabled repositories SHALL still be enqueued

#### Scenario: Scheduling disabled
- **GIVEN** the scheduled sync is disabled by configuration
- **WHEN** the worker starts
- **THEN** no scheduled sync SHALL run
