# repository-sync — incremental single-entity syncs

## ADDED Requirements

### Requirement: Incremental issue sync
The system SHALL support fetching and upserting a single issue by number for an enabled repository, without running a full repository sync. The upsert SHALL apply the same normalization and exclusions as the batch issue sync (pull requests are never stored as issues). After the upsert the repository's issue metrics SHALL be recomputed.

#### Scenario: Upsert one issue
- **WHEN** an incremental issue sync runs for issue #42 on an enabled repository
- **THEN** only issue #42 SHALL be fetched and upserted, and issue metrics SHALL be recomputed

#### Scenario: Incremental issue on a disabled repository
- **WHEN** an incremental issue sync is requested for a repository not enabled for indexing
- **THEN** no fetch or upsert SHALL occur

### Requirement: Incremental pull-request sync
The system SHALL support fetching and upserting a single pull request by number for an enabled repository, without a full sync, applying the same fields and derived timings as the batch PR sync, then recomputing PR metrics.

#### Scenario: Upsert one pull request
- **WHEN** an incremental PR sync runs for PR #61 on an enabled repository
- **THEN** only PR #61 SHALL be fetched and upserted, and PR metrics SHALL be recomputed
