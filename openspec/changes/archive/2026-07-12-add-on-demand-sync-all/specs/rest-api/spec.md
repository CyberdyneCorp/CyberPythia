# rest-api Specification

## ADDED Requirements

### Requirement: Trigger a full sync

`POST /api/v1/repos/sync-all` SHALL, for administrators, enqueue a sync for every
enabled repository (optionally filtered by an `organization` query parameter) and
return the enqueued/skipped counts.

#### Scenario: Full sync enqueued
- **WHEN** an administrator POSTs to `/api/v1/repos/sync-all`
- **THEN** the response SHALL contain the number of repositories enqueued and skipped
