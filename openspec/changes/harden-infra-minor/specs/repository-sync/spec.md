# repository-sync Specification

## MODIFIED Requirements

### Requirement: Raw payload snapshots
The system SHALL store raw GitHub API payloads (repository metadata, issues pages, PR pages, trees) in object storage (MinIO) keyed by repository and sync, for auditability and reprocessing. Object-storage keys SHALL be constrained to their intended prefix: a key containing a `..` path-traversal segment SHALL be rejected rather than written.

#### Scenario: Sync stores raw payloads
- **WHEN** any sync step fetches GitHub data
- **THEN** the raw response payload SHALL be persisted to object storage before normalization

#### Scenario: Traversing object key rejected
- **WHEN** a raw-snapshot key would contain a `..` traversal segment (e.g. from a malformed repository full name)
- **THEN** the write SHALL be rejected and no object SHALL be persisted outside the intended prefix
