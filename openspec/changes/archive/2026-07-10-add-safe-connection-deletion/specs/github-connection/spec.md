# github-connection Specification

## MODIFIED Requirements

### Requirement: Credential lifecycle
The system SHALL allow an admin to rotate (replace) or delete a credential.
Deleting a credential SHALL cascade-delete the repositories indexed under it and
their derived data, but SHALL do so **safely**: the number of repositories under
a connection SHALL be reported before deletion, the deletion SHALL run
asynchronously in the background worker (the connection is marked `deleting` and
removed on completion) so a large cascade cannot block or time out the request,
and callers SHALL be able to surface deletion failures.

#### Scenario: Credential rotation
- **WHEN** an admin replaces a credential for an owner
- **THEN** subsequent syncs SHALL use the new credential and the old value SHALL be destroyed

#### Scenario: Deletion is deferred to the worker
- **WHEN** an admin deletes a connection
- **THEN** the connection SHALL be marked `deleting` and a background job SHALL be enqueued to cascade-delete it and its repositories
- **AND** the connection SHALL be removed once the job completes

#### Scenario: Impact is known before deletion
- **WHEN** an admin lists connections
- **THEN** each connection SHALL report how many repositories are indexed under it
