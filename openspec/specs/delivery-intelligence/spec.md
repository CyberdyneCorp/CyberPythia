# delivery-intelligence Specification

## Purpose
TBD - created by archiving change add-delivery-intelligence-pm. Update Purpose after archive.
## Requirements
### Requirement: Flow metrics
The system SHALL expose per-repository flow metrics: cycle/lead-time percentiles (p50, p85,
p95) for issue resolution and PR merge, work-in-progress counts, and aging buckets of open
issues and PRs (0–7, 7–30, 30–90, 90+ days). Any percentile over an empty population SHALL be
reported as `null`.

#### Scenario: Percentiles for a repository with closed work
- **GIVEN** a repository with closed issues and merged PRs
- **WHEN** flow metrics are requested
- **THEN** the response SHALL include p50/p85/p95 cycle and merge times, WIP counts, and aging buckets

#### Scenario: No closed work
- **GIVEN** a repository with no closed issues
- **WHEN** flow metrics are requested
- **THEN** the resolution percentiles SHALL be `null` and labelled insufficient data

### Requirement: Untriaged backlog
The system SHALL report the count of open issues that lack a label and/or an assignee as a
grooming-debt signal.

#### Scenario: Untriaged issues surfaced
- **GIVEN** open issues without labels or assignees
- **WHEN** flow metrics are requested
- **THEN** the untriaged count SHALL be reported

### Requirement: Throughput and net-flow trend
The system SHALL expose, over the metrics time-series, a throughput trend (items closed per
period) and a net-flow trend (items created versus closed per period) for a repository. When
the series is too short to form a trend, the system SHALL report insufficient history rather
than a misleading value.

#### Scenario: Trend over accumulated history
- **GIVEN** a repository with several days of snapshots
- **WHEN** the throughput trend is requested
- **THEN** the system SHALL return closed-per-period points and the created-vs-closed net flow

#### Scenario: Insufficient history
- **GIVEN** a repository with fewer than the minimum snapshots
- **WHEN** a trend is requested
- **THEN** the system SHALL report insufficient history

### Requirement: Backlog forecast
The system SHALL project when a repository's open backlog will clear, using the trailing close
rate from the time-series applied to the current open count. When the backlog is not shrinking
(close rate ≤ arrival rate) or history is insufficient, the system SHALL return no projection
with an explicit reason.

#### Scenario: Backlog projected to clear
- **GIVEN** a repository whose trailing close rate exceeds its arrival rate
- **WHEN** a backlog forecast is requested
- **THEN** the system SHALL return a projected days-to-clear and date

#### Scenario: Backlog not shrinking
- **GIVEN** a repository whose backlog is growing
- **WHEN** a backlog forecast is requested
- **THEN** the system SHALL return no projection and the reason "backlog growing"

### Requirement: Work-mix
The system SHALL classify a repository's issues into work classes (feature, bug, tech-debt,
docs, other) via a configurable label-to-class map and report the distribution of issue counts
across classes, including the bug ratio.

#### Scenario: Work-mix distribution
- **GIVEN** a repository whose issues carry labels
- **WHEN** work-mix is requested
- **THEN** the response SHALL report the count per class and the bug ratio

### Requirement: Quality signals
The system SHALL report per-repository quality signals: bug ratio, reopened-issue rate, and
time-to-first-response percentiles. Signals whose underlying capture is absent SHALL be reported
as insufficient data, not as zero.

#### Scenario: Reopen rate with data
- **GIVEN** a repository whose issues carry reopened counts
- **WHEN** quality signals are requested
- **THEN** the reopened-issue rate SHALL be reported

#### Scenario: First-response not captured
- **GIVEN** a repository synced before first-response capture existed
- **WHEN** quality signals are requested
- **THEN** the time-to-first-response SHALL be reported as insufficient data

### Requirement: Milestone progress
The system SHALL report, per milestone of a repository, the percent complete
(closed / (open + closed)), a burn-up over the time-series, and a projected completion date
from the trailing close rate; the projection SHALL be flagged at-risk when it falls after the
milestone due date. A milestone without a due date or without sufficient history SHALL report
progress with no projection.

#### Scenario: Milestone on track
- **GIVEN** a milestone with a due date and a close rate that clears its open items before then
- **WHEN** milestone progress is requested
- **THEN** the system SHALL report percent complete and a projected date that is not at-risk

#### Scenario: Milestone at risk
- **GIVEN** a milestone whose projected completion is after its due date
- **WHEN** milestone progress is requested
- **THEN** the projection SHALL be flagged at-risk

### Requirement: Team load and concentration risk
The system SHALL report open-item load per assignee, reviewer load, and a bus-factor
(authorship-concentration) signal for a repository. The system SHALL report distribution and
risk only and SHALL NOT produce any per-person performance score or ranking.

#### Scenario: Concentration risk surfaced
- **GIVEN** a repository where a single author owns most pull requests
- **WHEN** team load is requested
- **THEN** the system SHALL report the load distribution and a low bus factor as a risk
- **AND** the response SHALL NOT contain any per-person ranking or score

### Requirement: Portfolio delivery scorecard
The system SHALL aggregate the per-repository delivery metrics into a portfolio scorecard —
predictability, throughput direction, backlog trend, and at-risk milestones across repositories
— with repositories lacking data marked insufficient rather than omitted.

#### Scenario: Delivery scorecard across repositories
- **WHEN** the delivery scorecard is requested
- **THEN** the system SHALL return each repository's headline delivery signals and flag those with insufficient data

