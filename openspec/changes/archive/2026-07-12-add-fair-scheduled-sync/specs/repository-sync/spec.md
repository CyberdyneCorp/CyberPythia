# repository-sync Specification

## MODIFIED Requirements

### Requirement: Scheduled daily full sync
The system SHALL run a scheduled job at least once per day that enqueues a full sync for every
enabled repository, using each repository's configured indexing mode. The job SHALL skip a
repository whose sync is already pending or running (never enqueuing a duplicate), and a failure
to enqueue one repository SHALL NOT prevent the others from being enqueued. The schedule SHALL be
configurable and SHALL be disableable.

To avoid starving repositories when the GitHub rate budget cannot cover the whole set in one run,
the job SHALL enqueue repositories **least-recently-synced first** (repositories never synced
before those with the oldest `last_synced_at`). The job MAY cap the number of repositories
enqueued per run via configuration (unbounded by default); when capped, the remaining
repositories are deferred to a later run and, because they remain least-recently-synced, are
prioritised then.

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

#### Scenario: Least-recently-synced repositories are enqueued first
- **WHEN** the scheduled sync runs
- **THEN** repositories SHALL be enqueued ordered by `last_synced_at` ascending (never-synced first), so a repository that failed to sync previously is prioritised on the next run

#### Scenario: Per-run cap defers the remainder
- **GIVEN** a per-run cap smaller than the number of enabled repositories
- **WHEN** the scheduled sync runs
- **THEN** at most that many repositories SHALL be enqueued, the least-recently-synced ones, and the rest SHALL be deferred to a later run
