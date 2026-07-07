# metrics-history — metrics time-series

## ADDED Requirements

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
The system SHALL provide a retention operation that keeps daily granularity for recent history
and coarser granularity for older history, so the series does not grow without bound. Retention
SHALL run off the request path.

#### Scenario: Old points are downsampled
- **GIVEN** a repository with snapshots older than the daily-retention window
- **WHEN** retention runs
- **THEN** older points SHALL be reduced to the coarser granularity and recent points preserved

### Requirement: History reads for analytics
The system SHALL expose the snapshot series for a repository over a bounded window so trend and
forecast analytics can read it. A repository with no snapshots SHALL yield an empty series, not
an error.

#### Scenario: Read a repository's series
- **WHEN** the delivery analytics request a repository's metrics history for a window
- **THEN** the system SHALL return the snapshots in that window in chronological order
