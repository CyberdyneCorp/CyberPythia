# rest-api — FastAPI interface

## ADDED Requirements

### Requirement: REST endpoint surface
The system SHALL expose a versioned REST API (`/api/v1`) with at minimum:

```text
POST   /api/v1/github/connect              (admin)
GET    /api/v1/github/connections          (admin)
POST   /api/v1/github/connections/{id}/test (admin)
DELETE /api/v1/github/connections/{id}     (admin)
GET    /api/v1/repos                        (discovered repositories + selection state)
PATCH  /api/v1/repos/{repo_id}              (admin: enable/disable, set indexing mode)
POST   /api/v1/repos/{repo_id}/sync         (admin)
GET    /api/v1/repos/{repo_id}/sync-status
GET    /api/v1/repos/{repo_id}/summary
GET    /api/v1/repos/{repo_id}/docs
GET    /api/v1/repos/{repo_id}/docs/{doc_id}
GET    /api/v1/repos/{repo_id}/openspec
GET    /api/v1/repos/{repo_id}/issues
GET    /api/v1/repos/{repo_id}/pull-requests
GET    /api/v1/repos/{repo_id}/files
GET    /api/v1/repos/{repo_id}/metrics
POST   /api/v1/repos/{repo_id}/search       (semantic doc search)
POST   /api/v1/repos/{repo_id}/ask
POST   /api/v1/repos/{repo_id}/context-pack
GET    /api/v1/health                        (unauthenticated)
```

All endpoints except `/api/v1/health` SHALL enforce the auth capability's bearer validation and entitlement gating; endpoints marked admin SHALL additionally enforce admin authorization.

#### Scenario: OpenAPI documentation
- **WHEN** a client fetches `/openapi.json`
- **THEN** every endpoint above SHALL be documented with request/response schemas and security requirements

#### Scenario: Health check without auth
- **WHEN** an unauthenticated client calls `GET /api/v1/health`
- **THEN** the system SHALL return service status including database, Redis, and object-storage reachability

### Requirement: Pagination and filtering
List endpoints (repos, docs, issues, pull-requests, files) SHALL support cursor- or page-based pagination with a bounded page size, and issues/PR endpoints SHALL support filtering by state and label/author.

#### Scenario: Paginated issues
- **WHEN** a client lists issues for a repository with more items than the page size
- **THEN** the response SHALL include a next-page cursor and SHALL NOT exceed the maximum page size

### Requirement: Consistent error model
The API SHALL return a consistent JSON error shape (machine-readable code, human message, correlation id) for all errors, and SHALL map domain errors to appropriate status codes (400 validation, 401 unauthenticated, 403 unauthorized, 404 unknown resource, 409 conflicting sync, 429 rate limited).

#### Scenario: Sync conflict
- **WHEN** a sync is triggered while one is already running for the repository
- **THEN** the API SHALL respond 409 with a code identifying the running sync
