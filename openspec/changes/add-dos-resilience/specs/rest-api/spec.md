# rest-api Specification

## ADDED Requirements

### Requirement: Request rate limiting

The REST API SHALL rate-limit requests to protect against resource-exhaustion
abuse (CWE-770). Limits SHALL be keyed by the caller's credential when present
and by the client IP otherwise. The system SHALL enforce a configurable global
default limit on every route, a stricter configurable limit on the cost-bearing
LLM/embedding routes (`POST /api/v1/repos/{repo_id}/ask`,
`/context-pack`, `/feature-document`, `/search`, `/code-search`, and
`GET /api/v1/intelligence/search`), and a configurable limit on the
unauthenticated `POST /api/v1/webhooks/github` and `GET /api/v1/health`
endpoints. When a caller exceeds a limit the system SHALL respond `429` in the
standard error envelope with a `Retry-After` header. Rate limiting SHALL be
configurable and disableable via settings.

#### Scenario: Exceeding a limit returns 429
- **WHEN** a caller sends more requests to a rate-limited endpoint than its configured limit within the window
- **THEN** the API SHALL respond `429` with a `Retry-After` header and the standard error body

#### Scenario: Cost-bearing routes use a stricter bucket
- **WHEN** a caller calls an LLM/embedding route (e.g. `/ask` or `/intelligence/search`)
- **THEN** the request SHALL be limited by the stricter cost-bearing limit rather than the global default

#### Scenario: Rate limiting disabled
- **WHEN** rate limiting is disabled via settings
- **THEN** requests SHALL NOT be throttled

### Requirement: Webhook payload size cap

The GitHub webhook receiver SHALL reject payloads larger than a configurable
maximum (default 1 MiB) with `413`, enforced before the body is parsed and
before its HMAC signature is verified. The cap SHALL be checked against the
declared `Content-Length` when present and against the actual received byte
length.

#### Scenario: Oversized body rejected before signature processing
- **WHEN** an unauthenticated client posts a webhook body larger than the configured cap
- **THEN** the API SHALL respond `413` without parsing the body or verifying its signature

#### Scenario: Oversized declared Content-Length rejected
- **WHEN** a webhook request declares a `Content-Length` above the cap
- **THEN** the API SHALL respond `413` before reading the body

### Requirement: Bounded result-count parameters

The API SHALL constrain every user-supplied `limit` query parameter that flows
into a database `LIMIT` to the range `1..MAX_PAGE_SIZE`, the same bound used by
paginated list endpoints, and SHALL reject values outside that range with `422`.

#### Scenario: Oversized limit rejected
- **WHEN** a client requests a `limit` greater than `MAX_PAGE_SIZE` on an endpoint that accepts one (e.g. `/intelligence/search` or a memories listing)
- **THEN** the API SHALL respond `422` and SHALL NOT issue an unbounded query
