# rest-api Specification

## ADDED Requirements

### Requirement: Memory endpoints

The REST API SHALL expose, for entitled callers, `POST /api/v1/repos/{id}/memories`
(record a memory: `content`, `kind`), `GET /api/v1/repos/{id}/memories` (list,
optional `query` and `kind`), and `DELETE /api/v1/repos/{id}/memories/{memory_id}`
(delete). It SHALL also expose `POST` and `GET`
`/api/v1/intelligence/organizations/{org}/memories` for organization-scoped
memories.

#### Scenario: Create and list repository memories
- **WHEN** an entitled caller POSTs a memory to a repository and then GETs its memories
- **THEN** the created memory SHALL appear in the list

#### Scenario: Delete a memory
- **WHEN** an entitled caller DELETEs a memory by id
- **THEN** the response SHALL be `204` and the memory SHALL be gone
