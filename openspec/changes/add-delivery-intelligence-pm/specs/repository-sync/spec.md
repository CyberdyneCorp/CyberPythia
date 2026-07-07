# repository-sync — enriched capture for delivery metrics

## ADDED Requirements

### Requirement: Milestone capture
The system SHALL capture a repository's GitHub milestones as records including title, state,
due date (when set), and open/closed issue counts, and SHALL keep them in sync on each
repository sync. Issues already carry their milestone name; milestone progress joins on it.

#### Scenario: Milestones captured on sync
- **GIVEN** a repository with milestones on GitHub
- **WHEN** the repository is synced
- **THEN** each milestone SHALL be stored with its state, due date, and issue counts

#### Scenario: Milestone without a due date
- **GIVEN** a milestone with no due date
- **WHEN** it is captured
- **THEN** it SHALL be stored with a null due date and still counted for progress

### Requirement: Issue first-response capture
The system SHALL capture, where determinable, the timestamp of the first non-author response
on an issue, stored as a nullable field. When it cannot be determined, the field SHALL remain
null and downstream metrics SHALL treat it as insufficient data.

#### Scenario: First response recorded
- **GIVEN** an issue with a comment from someone other than its author
- **WHEN** the repository is synced
- **THEN** the issue's first-response timestamp SHALL be recorded

### Requirement: Issue reopened count capture
The system SHALL capture how many times an issue has been reopened, stored as a count that
defaults to zero.

#### Scenario: Reopened issue counted
- **GIVEN** an issue that was closed and reopened
- **WHEN** the repository is synced
- **THEN** the issue's reopened count SHALL reflect the reopen
