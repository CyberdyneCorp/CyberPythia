# rest-api Specification

## Purpose
TBD - created by archiving change add-github-context-memory-core. Update Purpose after archive.
## Requirements
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

### Requirement: Code-content REST endpoints
The REST API SHALL add:

```text
GET    /api/v1/repos/{repo_id}/files/{file_id}/content   (captured source content)
POST   /api/v1/repos/{repo_id}/code-search                (semantic code search)
GET    /api/v1/repos/{repo_id}/symbols                    (symbol lookup; ?name= filter)
GET    /api/v1/repos/{repo_id}/files/{file_id}/related    (related files)
```

All SHALL enforce bearer validation and the `mnemosyne` entitlement; they SHALL respect the repository's indexing mode and return the consistent error model. `code-search` and `symbols` on a repository not indexed for code SHALL return 409 with a code identifying that source is not indexed. File-content retrieval SHALL be audit-logged.

#### Scenario: Code search endpoint
- **WHEN** an entitled caller POSTs a query to `/code-search` for a `code_context` repository
- **THEN** the response SHALL list ranked source-chunk matches with path, symbol, line span, excerpt, and score

#### Scenario: Code search on non-code repository
- **WHEN** an entitled caller calls `/code-search` for a repository indexed below `code_context`
- **THEN** the API SHALL respond 409 with a code indicating source code is not indexed

#### Scenario: File content endpoint documented and secured
- **WHEN** the OpenAPI document is fetched
- **THEN** the four code endpoints SHALL be present with bearer security requirements

### Requirement: GitHub App and webhook REST endpoints
The REST API SHALL add:

```text
POST   /api/v1/github/app/connect                              (admin)
GET    /api/v1/github/app/installations/{connection_id}/repos  (admin)
POST   /api/v1/webhooks/github                                 (public, signature-gated)
GET    /api/v1/admin/webhook-deliveries                        (admin)
```

The admin endpoints SHALL enforce bearer validation and admin authorization. The webhook endpoint SHALL be exempt from bearer auth and instead gated by HMAC signature validation, and SHALL always respond quickly (enqueue work rather than process synchronously where processing is non-trivial). All SHALL use the consistent error model, except the webhook endpoint which returns GitHub-friendly 2xx/401 responses.

#### Scenario: App connect documented and secured
- **WHEN** the OpenAPI document is fetched
- **THEN** the four endpoints SHALL be present, the admin ones declaring bearer security and the webhook one declaring none

#### Scenario: Webhook responds promptly
- **WHEN** a valid delivery arrives
- **THEN** the endpoint SHALL acknowledge with a 2xx after enqueuing/handling, without blocking on a full sync

#### Scenario: Delivery log
- **WHEN** an admin requests `/admin/webhook-deliveries`
- **THEN** recent deliveries SHALL be returned with event, action, repository, outcome, and timestamp

### Requirement: Engineering-intelligence REST endpoints
The REST API SHALL expose engineering-intelligence endpoints under `/api/v1/intelligence`, each requiring the same bearer authentication and `mnemosyne` entitlement as existing admin/query endpoints:

- `GET /api/v1/intelligence/portfolio` — portfolio overview (leaderboard, most-active, abandoned, bug-heavy).
- `GET /api/v1/intelligence/repositories/{id}/health` — repository health score, grade, components, findings.
- `GET /api/v1/intelligence/repositories/{id}/delivery` — delivery metrics.
- `GET /api/v1/intelligence/repositories/{id}/backlog` — backlog metrics.
- `GET /api/v1/intelligence/repositories/{id}/review-bottlenecks` — review-bottleneck analysis.
- `GET /api/v1/intelligence/repositories/{id}/maintenance-risk` — maintenance-risk assessment.
- `GET /api/v1/intelligence/repositories/{id}/onboarding` — onboarding summary.
- `POST /api/v1/intelligence/compare` — compare a set of repository ids.

Endpoints SHALL return a well-formed response with insufficient-data markers when metrics are absent, and SHALL return the standard not-found error for an unknown repository id.

#### Scenario: Fetch repository health over REST
- **GIVEN** an authenticated, entitled caller and a synced repository
- **WHEN** `GET /api/v1/intelligence/repositories/{id}/health` is called
- **THEN** the response SHALL contain the overall score, grade, component breakdown, and findings

#### Scenario: Portfolio endpoint
- **WHEN** `GET /api/v1/intelligence/portfolio` is called by an entitled caller
- **THEN** the response SHALL contain the leaderboard and the most-active, abandoned, and bug-heavy groupings

#### Scenario: Unknown repository
- **WHEN** an intelligence endpoint is called with an id that does not exist
- **THEN** the API SHALL return a not-found error

#### Scenario: Missing entitlement rejected
- **GIVEN** a caller authenticated without the `mnemosyne` entitlement
- **WHEN** any intelligence endpoint is called
- **THEN** the API SHALL reject the request as forbidden

### Requirement: Delivery-intelligence REST endpoints
The REST API SHALL expose PM/PO delivery endpoints, each requiring the same bearer
authentication and `mnemosyne` entitlement as existing intelligence endpoints:

- `GET /api/v1/intelligence/repositories/{id}/flow` — percentiles, WIP, aging, untriaged.
- `GET /api/v1/intelligence/repositories/{id}/throughput` — throughput and net-flow trend.
- `GET /api/v1/intelligence/repositories/{id}/forecast` — backlog forecast.
- `GET /api/v1/intelligence/repositories/{id}/work-mix` — work-class distribution and bug ratio.
- `GET /api/v1/intelligence/repositories/{id}/quality` — bug ratio, reopen rate, first-response.
- `GET /api/v1/intelligence/repositories/{id}/milestones` — per-milestone progress and projection.
- `GET /api/v1/intelligence/repositories/{id}/team-load` — load distribution and bus factor.
- `GET /api/v1/intelligence/delivery-scorecard` — portfolio delivery scorecard.

Endpoints SHALL return insufficient-data markers when metrics or history are absent and SHALL
return the standard not-found error for an unknown repository id.

#### Scenario: Fetch flow metrics over REST
- **GIVEN** an authenticated, entitled caller and a repository with closed work
- **WHEN** `GET /api/v1/intelligence/repositories/{id}/flow` is called
- **THEN** the response SHALL contain cycle/lead percentiles, WIP, and aging buckets

#### Scenario: Milestones endpoint flags at-risk
- **GIVEN** a repository with a milestone projected to miss its due date
- **WHEN** `GET /api/v1/intelligence/repositories/{id}/milestones` is called
- **THEN** the response SHALL mark that milestone at-risk

#### Scenario: Unknown repository
- **WHEN** a delivery endpoint is called with an id that does not exist
- **THEN** the API SHALL return a not-found error

#### Scenario: Missing entitlement rejected
- **GIVEN** a caller authenticated without the `mnemosyne` entitlement
- **WHEN** any delivery endpoint is called
- **THEN** the API SHALL reject the request as forbidden

### Requirement: Scheduled-run and sync-job admin endpoints
The REST API SHALL expose admin-only endpoints to observe sync activity:

- `GET /api/v1/admin/sync-runs` — recent scheduled-run summaries (timestamps, trigger, discovery
  and sync counters), newest first.
- `GET /api/v1/admin/sync-jobs` — recent per-repository sync jobs with the repository name, status,
  trigger, start/finish times, and any failed-step error messages.

Both endpoints SHALL require admin authorization and SHALL reject non-admin callers.

#### Scenario: Admin lists recent scheduled runs
- **GIVEN** an admin caller and at least one recorded scheduled run
- **WHEN** `GET /api/v1/admin/sync-runs` is called
- **THEN** the response SHALL list the run summaries newest first

#### Scenario: Admin sees a failed sync and its reason
- **GIVEN** a sync job that failed (for example, rate-limited)
- **WHEN** `GET /api/v1/admin/sync-jobs` is called by an admin
- **THEN** the response SHALL include that job with its status and the failed-step error text

#### Scenario: Non-admin rejected
- **GIVEN** a caller without admin authorization
- **WHEN** either endpoint is called
- **THEN** the API SHALL reject the request

### Requirement: Organization list and toggle endpoints
The REST API SHALL expose admin-only endpoints to manage organization sync scope:

- `GET /api/v1/github/organizations` — list organizations with `sync_enabled` and repository
  counts (total and enabled).
- `PATCH /api/v1/github/organizations/{login}` — set an organization's `sync_enabled` flag.

Both SHALL require admin authorization and reject non-admin callers.

#### Scenario: Admin lists organizations
- **GIVEN** an admin caller and discovered organizations
- **WHEN** `GET /api/v1/github/organizations` is called
- **THEN** the response SHALL list each organization with its sync flag and repo counts

#### Scenario: Admin disables an organization
- **GIVEN** an admin caller
- **WHEN** `PATCH /api/v1/github/organizations/{login}` sets sync disabled
- **THEN** the organization SHALL be persisted as sync-disabled

#### Scenario: Non-admin rejected
- **GIVEN** a caller without admin authorization
- **WHEN** either endpoint is called
- **THEN** the API SHALL reject the request

### Requirement: Filter repositories by organization
The repositories list endpoint SHALL accept an optional `organization` parameter that filters the
result to repositories whose owner matches the value (case-insensitive). The filter SHALL combine
with the existing enabled-only and pagination parameters.

#### Scenario: Filter to one organization
- **GIVEN** repositories across several organizations
- **WHEN** `GET /api/v1/repos?organization=cyberdynecorp` is called by an entitled caller
- **THEN** only repositories owned by that organization SHALL be returned

#### Scenario: No organization filter returns all
- **WHEN** the repositories list is called without an organization parameter
- **THEN** repositories across all organizations SHALL be returned as before

### Requirement: Bulk repository selection endpoint
The REST API SHALL provide an admin-only endpoint to set the enabled state (and optionally the
indexing mode) for a list of repositories in a single request, returning the number of
repositories updated. Repository ids that do not exist SHALL be ignored rather than failing the
request.

#### Scenario: Bulk enable a set of repositories
- **GIVEN** an admin caller and a list of repository ids
- **WHEN** `POST /api/v1/repos/selection` is called with `enabled: true` and a mode
- **THEN** each listed repository SHALL be enabled in that mode and the updated count returned

#### Scenario: Bulk disable
- **WHEN** the endpoint is called with `enabled: false` for a list of repositories
- **THEN** each listed repository SHALL be disabled

#### Scenario: Non-admin rejected
- **GIVEN** a caller without admin authorization
- **WHEN** the endpoint is called
- **THEN** the API SHALL reject the request

### Requirement: Bulk selection by organization
The bulk repository-selection endpoint SHALL accept an `organization` as an alternative to an
explicit list of repository ids, applying the enable/disable (and optional mode) to every
repository in that organization in a single request, and returning the number updated. The request
SHALL require either a repository-id list or an organization.

#### Scenario: Un-index a whole organization
- **GIVEN** an admin caller and an organization with several repositories
- **WHEN** `POST /api/v1/repos/selection` is called with that `organization` and `enabled: false`
- **THEN** every repository in that organization SHALL be disabled and the count returned

#### Scenario: Index a whole organization in a mode
- **WHEN** the endpoint is called with an `organization`, `enabled: true`, and a mode
- **THEN** every repository in that organization SHALL be enabled in that mode

#### Scenario: Neither ids nor organization
- **WHEN** the endpoint is called with neither repository ids nor an organization
- **THEN** the request SHALL be rejected as invalid

### Requirement: API key management endpoints

The system SHALL expose admin-only REST endpoints to create, list, and revoke
Mnemosyne API keys under `/api/v1/api-keys`. Creation SHALL accept a human label
and an optional expiry (a number of days, or none for a non-expiring key) and
SHALL return the plaintext key exactly once in the creation response. Listing
SHALL return key metadata only (id, label, display prefix, creator, timestamps,
expiry, revoked state) and SHALL NOT return the plaintext or the hash. Every
creation and revocation SHALL be recorded as an audit event.

#### Scenario: Create a key
- **WHEN** an admin `POST`s `/api/v1/api-keys` with a label and optional `expires_in_days`
- **THEN** the system SHALL create the key, record an audit event, and respond 201 with the plaintext key, its id, display prefix, and computed `expires_at`

#### Scenario: Plaintext returned only once
- **WHEN** an admin lists keys via `GET /api/v1/api-keys`
- **THEN** the response SHALL contain metadata only and SHALL NOT include the plaintext key or its hash

#### Scenario: Revoke a key
- **WHEN** an admin `DELETE`s `/api/v1/api-keys/{id}`
- **THEN** the system SHALL mark the key revoked, record an audit event, and the key SHALL no longer authenticate

#### Scenario: Non-admin denied
- **WHEN** a non-admin caller invokes any `/api/v1/api-keys` management endpoint
- **THEN** the system SHALL respond 403

### Requirement: Cross-repository and capability REST endpoints

The REST API SHALL mirror the cross-repository and capability tools for entitled
callers: `GET /api/v1/intelligence/search` (query, `kind` of docs|code|issues,
optional `organization`, `limit`), `GET /api/v1/intelligence/stale-issues` and
`/stale-prs`, `GET /api/v1/intelligence/recent-activity`, and
`GET /api/v1/repos/find`. The search endpoint SHALL reject an invalid `kind` with a
422. `GET /api/v1/intelligence/portfolio` and `/delivery-scorecard` SHALL accept an
optional `organization` query parameter, and `GET
/api/v1/intelligence/organizations/{org}/intelligence` and
`/organizations/{org}/capabilities` SHALL return the organization rollup and
capability union. `GET /api/v1/repos/{id}/capabilities` SHALL return the repository
capability overview and `POST /api/v1/repos/{id}/feature-document` SHALL return a
grounded Markdown features document.

#### Scenario: Search endpoint
- **WHEN** an entitled caller GETs `/api/v1/intelligence/search?query=…&kind=docs`
- **THEN** the response SHALL contain ranked results across indexed repositories, each with its repository identity

#### Scenario: Invalid search kind rejected
- **WHEN** the `kind` parameter is not docs, code, or issues
- **THEN** the API SHALL respond 422

#### Scenario: Organization-scoped portfolio
- **WHEN** an entitled caller GETs `/api/v1/intelligence/portfolio?organization=…`
- **THEN** the response SHALL include only that organization's repositories

#### Scenario: Repository capabilities and feature document
- **WHEN** an entitled caller GETs `/api/v1/repos/{id}/capabilities` or POSTs `/api/v1/repos/{id}/feature-document`
- **THEN** the API SHALL return the capability overview or a grounded Markdown features document respectively

