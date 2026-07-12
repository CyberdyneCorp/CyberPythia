# auth Specification

## MODIFIED Requirements

### Requirement: Bearer token validation via CyberdyneAuth
The system SHALL require a CyberdyneAuth-issued bearer token on every REST and MCP request except health checks and public metadata endpoints. The system SHALL validate tokens locally by verifying the RS256 signature against the CyberdyneAuth JWKS (`/.well-known/jwks.json`), the issuer (`OIDC_ISSUER`), and the expiry. The JWKS SHALL be cached and refreshed on unknown-`kid` or on a configurable TTL. To prevent a pre-authentication caller from amplifying JWKS traffic by streaming random `kid` values (CWE-770), an unknown `kid` SHALL trigger at most one JWKS refetch per configurable minimum-refresh window (`AUTH_JWKS_MIN_REFRESH_SECONDS`); within that window an unknown `kid` SHALL be treated as unknown without a refetch, while the TTL-based refresh is unaffected. When a validated token carries an audience (`aud`) claim, that audience MUST include the configured `SERVICE_AUDIENCE`; a token whose `aud` does not match SHALL be rejected, while a token with no `aud` (user tokens) remains valid (CWE-287).

#### Scenario: Valid user token
- **WHEN** a request carries a bearer token signed by CyberdyneAuth with a valid `kid`, `iss`, and unexpired `exp`
- **THEN** the system SHALL resolve the caller identity (`sub`, `username`, `scope`, `is_admin`, `entitlements`) and process the request

#### Scenario: Invalid or expired token
- **WHEN** a request carries a token with an invalid signature, wrong issuer, or expired `exp`
- **THEN** the system SHALL respond 401 without revealing which check failed

#### Scenario: Missing token
- **WHEN** a request to a protected endpoint carries no `Authorization` header
- **THEN** the system SHALL respond 401

#### Scenario: Unknown-kid refetch is throttled
- **WHEN** many tokens carrying distinct unknown `kid` values are presented within the minimum-refresh window
- **THEN** the system SHALL perform at most one JWKS refetch for the window and reject each token with an unknown-signing-key error

#### Scenario: Token with a mismatched audience is rejected
- **WHEN** a token carries an `aud` claim that does not include the configured `SERVICE_AUDIENCE`
- **THEN** the system SHALL respond 401

#### Scenario: Token without an audience is accepted
- **WHEN** an otherwise valid user token carries no `aud` claim
- **THEN** the system SHALL resolve the caller identity and process the request

### Requirement: Admin-only operations
The system SHALL restrict credential management (GitHub connection create/update/delete), repository indexing selection, and sync triggering to callers with `is_admin: true` or an `mnemosyne:admin` scope. For these sensitive operations, when `AUTH_FORCE_INTROSPECT_ADMIN` is enabled (default), the system SHALL re-validate the presented token through the revocation-aware introspection path regardless of any entitlements the token embeds locally, so that a revoked-but-unexpired token cannot administer (CWE-613); a token that introspection reports inactive SHALL be rejected with 401.

#### Scenario: Non-admin attempts to connect GitHub
- **WHEN** an entitled but non-admin caller invokes `POST /github/connect`
- **THEN** the system SHALL respond 403

#### Scenario: Revoked token cannot administer
- **WHEN** a caller presents a structurally valid, entitlement-bearing JWT that introspection reports as revoked (`active: false`) to an admin-only operation
- **THEN** the system SHALL respond 401 even though the JWT signature is locally valid

## ADDED Requirements

### Requirement: Read-only credential write protection
Mnemosyne API keys SHALL be read/query-only credentials: the resolved caller identity SHALL carry a read-only marker, and such callers SHALL be denied every mutating operation even when they hold the required entitlement (CWE-269). This applies to the mutating MCP tools (`mnemosyne_remember`, `mnemosyne_forget`) and the REST memory write/delete endpoints (repository memory create/delete and organization memory create). Read and query operations SHALL continue to succeed for read-only credentials.

#### Scenario: Read-only credential denied on a mutating MCP tool
- **WHEN** a read-only credential invokes `mnemosyne_remember` or `mnemosyne_forget`
- **THEN** the tool SHALL return an error and perform no write

#### Scenario: Read-only credential denied on a REST memory write
- **WHEN** a read-only credential calls a repository or organization memory create/delete endpoint
- **THEN** the system SHALL respond 403 with a `read_only` error code

#### Scenario: Read-only credential can still read
- **WHEN** a read-only credential lists or recalls memories
- **THEN** the request SHALL be processed

#### Scenario: Non-read-only caller may write
- **WHEN** an entitled, non-read-only caller creates a memory
- **THEN** the request SHALL be processed

### Requirement: Organization-scoped document access
Document-detail access SHALL be filtered by the caller's accessible organizations. `GET /api/v1/repos/{repo_id}/docs/{doc_id}` SHALL resolve the repository through the org-scoped repository lookup — which returns 404 for a repository outside the caller's accessible organizations — before fetching the document, so a caller cannot read a document belonging to an out-of-scope repository by knowing its identifiers (CWE-639/BOLA).

#### Scenario: Out-of-scope document is not found
- **WHEN** a caller scoped to organization A requests a document of a repository owned by organization B
- **THEN** the system SHALL respond 404

#### Scenario: In-scope or unrestricted document access succeeds
- **WHEN** an unrestricted (or in-scope) caller requests a document of an accessible repository
- **THEN** the system SHALL return the document
