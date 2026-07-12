# rest-api Specification

## MODIFIED Requirements

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
GET    /api/v1/health                        (unauthenticated, minimal status)
GET    /api/v1/admin/health                  (admin: per-component detail)
```

All endpoints except `/api/v1/health` SHALL enforce the auth capability's bearer validation and entitlement gating; endpoints marked admin SHALL additionally enforce admin authorization.

#### Scenario: OpenAPI documentation
- **WHEN** a client fetches `/openapi.json`
- **THEN** every endpoint above SHALL be documented with request/response schemas and security requirements

#### Scenario: Public health check without auth
- **WHEN** an unauthenticated client calls `GET /api/v1/health`
- **THEN** the system SHALL respond HTTP 200 while serving with a minimal overall status (`ok` or `degraded`) only, and SHALL NOT disclose per-component reachability or failing exception class names

#### Scenario: Admin health check exposes component detail
- **WHEN** an admin caller calls `GET /api/v1/admin/health`
- **THEN** the system SHALL return the overall status plus a per-component reachability map (database, Redis, object storage)

#### Scenario: Component detail requires admin authorization
- **WHEN** `GET /api/v1/admin/health` is called without a bearer token, or by a non-admin caller
- **THEN** the request SHALL be rejected (401 unauthenticated or 403 unauthorized) and no component detail SHALL be returned
