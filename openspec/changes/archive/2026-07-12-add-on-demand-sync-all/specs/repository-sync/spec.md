# repository-sync Specification

## ADDED Requirements

### Requirement: On-demand full sync

The system SHALL let an admin trigger an immediate sync of all enabled
repositories, optionally scoped to a single organization, reusing the per-repo
enqueue path (holding the per-repository lock so an already-running sync is
skipped, and continuing past individual failures). It SHALL report how many
repositories were enqueued and how many were skipped.

#### Scenario: Sync all enabled repositories
- **WHEN** an admin triggers an on-demand full sync
- **THEN** a sync SHALL be enqueued for each enabled repository not already running, and the counts of enqueued and skipped SHALL be returned

#### Scenario: Scoped to an organization
- **WHEN** an admin triggers an on-demand sync scoped to an organization
- **THEN** only that organization's enabled repositories SHALL be enqueued
