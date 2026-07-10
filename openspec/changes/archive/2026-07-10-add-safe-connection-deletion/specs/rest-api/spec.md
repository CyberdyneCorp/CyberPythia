# rest-api Specification

## ADDED Requirements

### Requirement: Delete a GitHub connection

`DELETE /api/v1/github/connections/{id}` SHALL, for administrators, mark the
connection `deleting`, enqueue a background job to cascade-delete it and its
indexed repositories, and return `202 Accepted` with the number of repositories
scheduled for deletion. Connection responses SHALL include `repository_count`.

#### Scenario: Delete accepted for async processing
- **WHEN** an administrator DELETEs an existing connection
- **THEN** the response SHALL be `202` with the repository count and the connection SHALL be marked `deleting`

#### Scenario: Unknown connection
- **WHEN** an administrator DELETEs a connection that does not exist
- **THEN** the response SHALL be `404`
