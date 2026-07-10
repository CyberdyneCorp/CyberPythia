# engineering-intelligence Specification

## ADDED Requirements

### Requirement: Readiness history and regression detection

The intelligence layer SHALL record each repository's readiness gate at most once
per UTC day, building a per-repository time series. It SHALL expose a
repository's readiness trend, and an organization-level list of **regressions** —
repositories whose most recent recorded gate is lower than their previous
recorded gate (ranking MVP < READY < DONE) — including the previous gate, the
current gate, and the date the change was recorded.

Recording SHALL happen as part of the daily scheduled run, after syncing.
Historical gates SHALL NOT be back-filled; the series accrues from first record.

#### Scenario: Daily gate recorded
- **WHEN** the scheduled readiness recording runs for a repository
- **THEN** a snapshot with that day's gate SHALL be stored, and a second run on the same day SHALL update rather than duplicate it

#### Scenario: Regression surfaced
- **WHEN** a repository's latest recorded gate is lower than its previous recorded gate
- **THEN** the organization regressions view SHALL include it with its previous gate, current gate, and the date

#### Scenario: Stable or improving repositories are not regressions
- **WHEN** a repository's latest gate is equal to or higher than its previous gate
- **THEN** it SHALL NOT appear in the regressions view
