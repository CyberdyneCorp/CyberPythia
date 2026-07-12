# metrics-history Specification

## MODIFIED Requirements

### Requirement: Time-series retention
The system SHALL bound the growth of the per-repository daily snapshot series
(metrics and readiness) by deleting snapshots older than a configurable retention
window. Retention SHALL run off the request path (as part of the scheduled daily
run), SHALL be disableable (a window of 0 keeps everything), and SHALL not fail
the scheduled run on error.

#### Scenario: Old points are pruned
- **GIVEN** snapshots older than the configured retention window
- **WHEN** retention runs
- **THEN** those snapshots SHALL be deleted and snapshots within the window preserved

#### Scenario: Retention disabled
- **GIVEN** the retention window is configured to 0
- **WHEN** retention runs
- **THEN** no snapshots SHALL be deleted
