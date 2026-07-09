# auth Specification

## ADDED Requirements

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
