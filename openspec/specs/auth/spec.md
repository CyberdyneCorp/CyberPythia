# auth Specification

## Purpose
TBD - created by archiving change add-github-context-memory-core. Update Purpose after archive.
## Requirements
### Requirement: Bearer token validation via CyberdyneAuth
The system SHALL require a CyberdyneAuth-issued bearer token on every REST and MCP request except health checks and public metadata endpoints. The system SHALL validate tokens locally by verifying the RS256 signature against the CyberdyneAuth JWKS (`/.well-known/jwks.json`), the issuer (`OIDC_ISSUER`), and the expiry. The JWKS SHALL be cached and refreshed on unknown-`kid` or on a configurable TTL.

#### Scenario: Valid user token
- **WHEN** a request carries a bearer token signed by CyberdyneAuth with a valid `kid`, `iss`, and unexpired `exp`
- **THEN** the system SHALL resolve the caller identity (`sub`, `username`, `scope`, `is_admin`, `entitlements`) and process the request

#### Scenario: Invalid or expired token
- **WHEN** a request carries a token with an invalid signature, wrong issuer, or expired `exp`
- **THEN** the system SHALL respond 401 without revealing which check failed

#### Scenario: Missing token
- **WHEN** a request to a protected endpoint carries no `Authorization` header
- **THEN** the system SHALL respond 401

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
The system SHALL restrict credential management (GitHub connection create/update/delete), repository indexing selection, and sync triggering to callers with `is_admin: true` or an `mnemosyne:admin` scope.

#### Scenario: Non-admin attempts to connect GitHub
- **WHEN** an entitled but non-admin caller invokes `POST /github/connect`
- **THEN** the system SHALL respond 403

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

