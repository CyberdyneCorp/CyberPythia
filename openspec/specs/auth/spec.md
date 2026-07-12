# auth Specification

## Purpose
TBD - created by archiving change add-github-context-memory-core. Update Purpose after archive.
## Requirements
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

### Requirement: Token introspection fallback
The system SHALL support RFC 7662 introspection against `POST /api/v1/auth/introspect` as an alternative validation path, authenticating with Mnemosyne's own client-credentials service token. Introspection SHALL be used when local JWKS validation is unavailable or when authoritative revocation checking is configured (`AUTH_VALIDATION_MODE=introspect`).

#### Scenario: Revoked token caught by introspection
- **WHEN** introspection mode is active and CyberdyneAuth returns `active: false` for a presented token
- **THEN** the system SHALL respond 401 even if the JWT signature is locally valid

### Requirement: Entitlement gating
The system SHALL authorize callers by CyberdyneAuth claims, read from the validated token or introspection response — never from local state. Access SHALL be granted when any of the following holds:
- the caller is `is_admin`;
- a user token carries the configured product entitlement (`REQUIRED_ENTITLEMENT`, the Mnemosyne OAuth client's `client_id`), matching exactly or with a `:plan` suffix (CyberdyneAuth entitlement tokens are `product_key` or `product_key:plan`);
- a service token carries the configured audience (`SERVICE_AUDIENCE`) in `aud` — CyberdyneAuth entitlements are user-only, so agent clients are granted access via `allowed_audiences`.

#### Scenario: Caller without entitlement
- **WHEN** an authenticated caller without the required entitlement, audience, or `is_admin` invokes a data endpoint or MCP tool
- **THEN** the system SHALL respond 403 (REST) or return an MCP error result identifying missing entitlement

#### Scenario: Entitled user token
- **WHEN** a user token whose introspection response includes the product entitlement (with or without a `:plan` suffix) invokes a data endpoint
- **THEN** the request SHALL be processed

#### Scenario: Agent service token with the Mnemosyne audience
- **WHEN** a client-credentials service token minted with `audience=mnemosyne` invokes an MCP tool
- **THEN** the tool SHALL execute

#### Scenario: Agent service token without the audience
- **WHEN** a service token without the Mnemosyne audience invokes an MCP tool
- **THEN** the call SHALL be rejected as missing entitlement

### Requirement: Admin-only operations
The system SHALL restrict credential management (GitHub connection create/update/delete), repository indexing selection, and sync triggering to callers with `is_admin: true` or an `mnemosyne:admin` scope. For these sensitive operations, when `AUTH_FORCE_INTROSPECT_ADMIN` is enabled (default), the system SHALL re-validate the presented token through the revocation-aware introspection path regardless of any entitlements the token embeds locally, so that a revoked-but-unexpired token cannot administer (CWE-613); a token that introspection reports inactive SHALL be rejected with 401.

#### Scenario: Non-admin attempts to connect GitHub
- **WHEN** an entitled but non-admin caller invokes `POST /github/connect`
- **THEN** the system SHALL respond 403

#### Scenario: Revoked token cannot administer
- **WHEN** a caller presents a structurally valid, entitlement-bearing JWT that introspection reports as revoked (`active: false`) to an admin-only operation
- **THEN** the system SHALL respond 401 even though the JWT signature is locally valid

### Requirement: Web UI login via OIDC
The web UI SHALL authenticate users with the CyberdyneAuth OIDC authorization-code flow with PKCE (S256), using a registered public client, discovery at `<OIDC_ISSUER>/.well-known/openid-configuration`, and scopes `openid email profile offline_access`. The UI SHALL attach the resulting access token as a bearer token on API calls and SHALL use refresh-token rotation to stay signed in.

#### Scenario: User signs in with Connect with Cyberdyne
- **WHEN** an anonymous user clicks "Connect with Cyberdyne"
- **THEN** the UI SHALL redirect to the CyberdyneAuth authorization endpoint with PKCE and, on callback, SHALL exchange the code for tokens and establish the session

#### Scenario: Access token expires during a session
- **WHEN** an API call fails with 401 and a refresh token is held
- **THEN** the UI SHALL refresh via the token endpoint (rotating the refresh token) and retry once before signing the user out

### Requirement: Agent service authentication
The system SHALL accept client-credentials service tokens issued by CyberdyneAuth's token endpoint for agent and service-to-service access on both REST and MCP interfaces. Service identities SHALL be subject to the same entitlement gating as users.

#### Scenario: Agent obtains and uses a service token
- **WHEN** an agent exchanges its `client_id`/`client_secret` at the CyberdyneAuth token endpoint and presents the resulting token to the MCP server
- **THEN** the MCP server SHALL authenticate the agent as that service identity

### Requirement: No local credential storage for identities
The system SHALL NOT store passwords, issue its own identity tokens, or maintain a parallel user database. Locally persisted identity data SHALL be limited to the CyberdyneAuth `sub`, display metadata, and audit references.

#### Scenario: Identity data at rest
- **WHEN** a user or agent interacts with Mnemosyne
- **THEN** the only identity data persisted SHALL be the CyberdyneAuth subject id, display name/email snapshot, and audit log entries

### Requirement: Access auditing
The system SHALL write an audit record (caller `sub`, client id, operation, target repository, timestamp) for sensitive operations: GitHub credential changes, sync triggers, context-pack builds, and any denied (401/403) access to data endpoints.

#### Scenario: Denied access is audited
- **WHEN** a caller receives 403 on a data endpoint
- **THEN** an audit record SHALL be persisted with the caller identity and the denied operation

### Requirement: Webhook endpoint is signature-gated, not bearer-gated
The webhook receiver (`POST /api/v1/webhooks/github`) SHALL be exempt from the CyberdyneAuth bearer-token requirement, since GitHub cannot present a CyberdyneAuth token. It SHALL instead be gated by HMAC-SHA256 signature validation against the installation webhook secret. This is the only non-health endpoint permitted to bypass bearer validation, and it SHALL reject unsigned or mis-signed requests.

#### Scenario: Webhook without a bearer token
- **WHEN** GitHub calls the webhook endpoint with a valid signature but no `Authorization` header
- **THEN** the request SHALL be accepted (signature is the gate)

#### Scenario: Webhook with an invalid signature
- **WHEN** a request to the webhook endpoint has no valid signature
- **THEN** it SHALL be rejected with 401 regardless of any bearer token

### Requirement: Mnemosyne API keys as an alternative bearer credential

The system SHALL accept a Mnemosyne-issued API key as an alternative bearer
credential on both REST and MCP requests, in addition to CyberdyneAuth tokens.
An API key SHALL be a string with the reserved prefix `mnem_` followed by a
high-entropy secret. The system SHALL store only a SHA-256 hash of the key and
SHALL NOT persist the plaintext. A presented bearer that begins with `mnem_`
SHALL be validated against stored keys; any other bearer SHALL be validated by
the existing CyberdyneAuth path unchanged.

A valid API key SHALL resolve to a caller identity that carries the required
`mnemosyne` entitlement (read/query access). An API-key caller SHALL NOT be
treated as an administrator and SHALL be denied admin-only operations.

An API key MAY carry an optional organization boundary. A key with no boundary
(the default, and every key issued before this capability) SHALL be unrestricted
across all organizations. A key configured with a non-empty organization list
SHALL be restricted to exactly those organizations (case-insensitive), using the
**same** per-organization boundary mechanism as user tokens — not a separate
authorization path. The create flow SHALL accept an optional organization list,
normalise it to lower-case, and treat an empty selection as unrestricted.

#### Scenario: Valid API key grants query access
- **WHEN** a request carries a bearer token beginning with `mnem_` whose SHA-256 hash matches a stored key that is not revoked and not expired
- **THEN** the system SHALL resolve a caller with the `mnemosyne` entitlement and process the request as an entitled (non-admin) caller

#### Scenario: Unknown API key
- **WHEN** a request carries an `mnem_` bearer whose hash matches no stored key
- **THEN** the system SHALL respond 401 (REST) or raise an unauthenticated tool error (MCP)

#### Scenario: Expired API key
- **WHEN** a request carries an `mnem_` bearer whose stored key has an `expires_at` in the past
- **THEN** the system SHALL reject it as unauthenticated

#### Scenario: Revoked API key
- **WHEN** a request carries an `mnem_` bearer whose stored key has been revoked
- **THEN** the system SHALL reject it as unauthenticated

#### Scenario: Non-API-key bearer is unaffected
- **WHEN** a request carries a bearer token that does not begin with `mnem_`
- **THEN** the system SHALL validate it via CyberdyneAuth exactly as before

#### Scenario: API key cannot perform admin operations
- **WHEN** a caller authenticated by an API key invokes an admin-only endpoint
- **THEN** the system SHALL respond 403 (administrator privileges required)

#### Scenario: Unscoped API key is unrestricted
- **WHEN** a request is authenticated by an API key that carries no organization boundary
- **THEN** the caller SHALL access repositories and memories across all indexed organizations

#### Scenario: Org-scoped API key is denied cross-org data
- **WHEN** a request is authenticated by an API key restricted to organization `cyberdyne` and reads a repository or memory owned by a different organization
- **THEN** the out-of-scope resource SHALL be treated as not found, while `cyberdyne` resources remain accessible

### Requirement: MCP OAuth protected resource

When MCP OAuth is enabled, the MCP server SHALL behave as an OAuth protected
resource whose user tokens are issued by CyberdyneAuth via a bridging proxy.
Access tokens obtained through the flow SHALL be ordinary CyberdyneAuth user JWTs
and SHALL be validated by the existing validation path (JWKS signature/issuer/
expiry with introspection fallback) and authorized by the existing `mnemosyne`
entitlement rule — no separate authorization model, no audience binding required.
The upstream client credentials used for the bridge SHALL be held only in server
configuration and never persisted with user identities.

#### Scenario: Proxy-issued token validated like any CyberdyneAuth token
- **WHEN** a request carries an access token minted through the MCP OAuth proxy
- **THEN** the system SHALL verify it against CyberdyneAuth exactly as it verifies any bearer token, granting access only on a valid signature and the `mnemosyne` entitlement

#### Scenario: Authenticated user without the entitlement is rejected
- **WHEN** a token presented to the MCP server belongs to a user who lacks the `mnemosyne` entitlement
- **THEN** the system SHALL reject the tool call with a missing-entitlement error

#### Scenario: Upstream client secret not stored with identities
- **WHEN** the proxy performs the upstream code exchange
- **THEN** the upstream client secret SHALL be read from configuration only and SHALL NOT be written to the identity/credential store

### Requirement: Per-organization access scoping

The system SHALL maintain a request/tool-scoped organization boundary with three
states: **unset** (deny-all), **unrestricted** (all organizations), and a
restricted set of organizations. The boundary SHALL default to **unset**: with no
boundary established, every organization SHALL be treated as inaccessible
(fail-closed, CWE-284).

A caller's accessible organizations SHALL be derived from CyberdyneAuth
entitlements: a caller who is `is_admin`, holds the bare product entitlement, or
is admitted by service audience SHALL be unrestricted; a caller whose only grant
is one or more plan-qualified entitlements (`product_key:<org>`) SHALL be
restricted to exactly those organizations (case-insensitive). The system SHALL
set this boundary as soon as a caller's identity is proven — on the base
authenticated dependency, not only the entitled dependency — so no authenticated
request path is left at the unset default or an unrestricted view (FINDING-025).

Every read of repository or organization data SHALL be limited to the boundary: a
repository outside scope SHALL be treated as not found, and organization-scoped,
cross-repository, and portfolio results SHALL exclude out-of-scope organizations.
An **unset** boundary SHALL expose no organizations.

Entrypoints that run without a per-caller identity but legitimately span every
organization — background worker jobs (repository sync, connection deletion,
scheduled discovery/sync) and signature-authenticated webhook processing — SHALL
explicitly grant the unrestricted state at entry. They SHALL NOT rely on the
default being unrestricted.

#### Scenario: Unset boundary denies every organization
- **WHEN** repository or organization data is read with no organization boundary established
- **THEN** every organization SHALL be treated as inaccessible (out-of-scope repositories not found; rollups empty)

#### Scenario: Org-scoped caller sees only its organization
- **WHEN** a caller whose entitlement is `mnemosyne:CyberdyneCorp` lists repositories
- **THEN** only `CyberdyneCorp` repositories SHALL be returned

#### Scenario: Out-of-scope repository is not found
- **WHEN** an org-scoped caller requests a repository in a different organization by id
- **THEN** the response SHALL be 404 (REST) or a not-found error (MCP)

#### Scenario: Unscoped caller sees everything
- **WHEN** a caller holds the bare `mnemosyne` entitlement or is `is_admin`
- **THEN** repositories across all indexed organizations SHALL be accessible

#### Scenario: Background worker job reaches every organization
- **WHEN** a worker job (e.g. the scheduled full sync) runs with no request or caller
- **THEN** it SHALL explicitly grant the unrestricted state and access all enabled repositories across every organization, despite the fail-closed default

#### Scenario: Webhook processing reaches the target repository
- **WHEN** a signature-authenticated webhook is processed with no bearer caller
- **THEN** processing SHALL explicitly grant the unrestricted state so the target repository is visible to incremental sync

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

### Requirement: MCP tools authenticate through a central choke point

The MCP server SHALL enforce authentication and organization scoping for every
tool invocation at a single central choke point (a server middleware) that runs
before the tool body executes, so a newly added tool cannot be served
unauthenticated or unscoped (CWE-1188). The choke point SHALL authenticate the
caller, apply the caller's organization boundary, and — for mutating tools —
reject read/query-only credentials (e.g. API keys). Read-only tools SHALL remain
callable by read-only credentials.

#### Scenario: Tool with no in-body auth is still authenticated
- **WHEN** a tool that does not itself perform authentication is invoked without a valid credential
- **THEN** the central choke point SHALL reject the call with an unauthenticated error before the tool body runs

#### Scenario: Central choke point applies the org boundary
- **WHEN** an org-scoped caller invokes any tool
- **THEN** the caller's organization boundary SHALL be in effect for the tool body, so out-of-scope organizations are inaccessible even if the tool does not scope itself

#### Scenario: Read-only credential rejected on a mutating tool
- **WHEN** a read/query-only credential invokes a mutating tool (e.g. remember/forget)
- **THEN** the central choke point SHALL reject the call as forbidden (read-only)

