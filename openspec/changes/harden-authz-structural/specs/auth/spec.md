# auth Specification

## MODIFIED Requirements

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

## ADDED Requirements

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
