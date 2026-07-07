# engineering-metrics — issue and PR metrics

## ADDED Requirements

### Requirement: Issue metrics computation
The system SHALL compute per-repository issue metrics from synced data: average and median resolution time (closed issues only), open issue age distribution, stale issue list (open with no activity for a configurable threshold, default 30 days), and counts by label and assignee.

#### Scenario: Average resolution time
- **WHEN** a repository has closed issues with known created/closed timestamps
- **THEN** the average and median resolution times SHALL be computed over closed issues only

#### Scenario: No closed issues
- **WHEN** a repository has no closed issues
- **THEN** resolution-time metrics SHALL be reported as absent (not zero)

#### Scenario: Stale issue detection
- **WHEN** an open issue has had no update for longer than the staleness threshold
- **THEN** it SHALL appear in the stale issues list with its age

### Requirement: Pull request metrics computation
The system SHALL compute per-repository PR metrics: average and median time to merge (merged PRs only), average time to first review (PRs with at least one review), merge rate (merged / closed), PR size distribution by additions+deletions buckets, stale open PRs, and counts by author and reviewer.

#### Scenario: Time to first review excludes unreviewed PRs
- **WHEN** computing average time to first review
- **THEN** PRs without any review SHALL be excluded from that average

#### Scenario: PR size distribution
- **WHEN** PR metrics are computed
- **THEN** each PR SHALL be bucketed by total changed lines (e.g., XS ≤10, S ≤100, M ≤500, L ≤1000, XL >1000)

### Requirement: Metrics freshness and provenance
Metrics SHALL be recomputed at the end of each successful repository sync and stored with the timestamp of the sync they derive from. Metric responses SHALL include that timestamp.

#### Scenario: Metrics after sync
- **WHEN** a sync completes successfully
- **THEN** the repository's metrics SHALL reflect the newly synced data and carry the sync timestamp

### Requirement: Repository summary
The system SHALL maintain a per-repository summary combining metadata, documentation presence (README/docs/OpenSpec found), issue/PR counts, and headline metrics, suitable for dashboards and agent consumption.

#### Scenario: Summary content
- **WHEN** a summary is requested for a synced repository
- **THEN** it SHALL include description, primary language, last sync time, documentation presence flags, open/closed issue counts, open PR count, and headline metrics
