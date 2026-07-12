# metrics-history Specification

## Purpose
TBD - created by archiving change add-delivery-intelligence-pm. Update Purpose after archive.
## Requirements
### Requirement: Metrics snapshot time-series
The system SHALL maintain an append-only per-repository metrics time-series. On every metrics
recompute (full sync and webhook-driven incremental sync), the system SHALL record a snapshot
capturing at least: open/closed issue counts, open/merged PR counts, throughput counters,
a cycle-time aggregate, the overall health score, and the capture timestamp. The system SHALL
store at most one snapshot per repository per UTC day; a later recompute on the same day SHALL
update that day's snapshot rather than appending a duplicate.

#### Scenario: Snapshot recorded on recompute
- **WHEN** a repository's metrics are recomputed
- **THEN** a snapshot for that repository and day SHALL be recorded or updated

#### Scenario: One snapshot per day
- **GIVEN** a repository already has a snapshot for the current UTC day
- **WHEN** its metrics are recomputed again the same day
- **THEN** that day's snapshot SHALL be updated in place, not duplicated

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

### Requirement: History reads for analytics
The system SHALL expose the snapshot series for a repository over a bounded window so trend and
forecast analytics can read it. A repository with no snapshots SHALL yield an empty series, not
an error.

#### Scenario: Read a repository's series
- **WHEN** the delivery analytics request a repository's metrics history for a window
- **THEN** the system SHALL return the snapshots in that window in chronological order

