# repository-sync — scheduled run history

## ADDED Requirements

### Requirement: Record scheduled run outcomes
The system SHALL record the outcome of each scheduled daily run as a persistent history entry
capturing the run's start and finish times, its trigger, the discovery counters (repositories
discovered, newly enabled, archived skipped), and the sync counters (enqueued, skipped, failed).

#### Scenario: A scheduled run is recorded
- **WHEN** the daily scheduled job completes
- **THEN** a history entry SHALL be recorded with its timestamps and discovery/sync counters

#### Scenario: History is listable newest-first
- **WHEN** the recorded scheduled runs are read
- **THEN** they SHALL be returned most-recent first
