# mcp-interface Specification

## ADDED Requirements

### Requirement: MCP OAuth connector flow

The MCP server SHALL support the MCP OAuth 2.1 authorization flow so that clients
which self-register (claude.ai, Claude Desktop) can connect with no manually
supplied token. The server SHALL act as an OAuth authorization server **from the
client's perspective** by serving protected-resource metadata, authorization-server
metadata, a dynamic-client-registration endpoint, and authorization + token
endpoints, and SHALL bridge the authorization to CyberdyneAuth using a single
pre-registered upstream client. The authorization-code exchange SHALL use PKCE
(S256). The resulting user token SHALL authorize tool calls through the existing
`mnemosyne` entitlement check (no audience binding required). The flow SHALL be
feature-flagged and disabled by default.

#### Scenario: Protected-resource metadata advertised
- **WHEN** a client requests `/.well-known/oauth-protected-resource` from the MCP server with OAuth enabled
- **THEN** the server SHALL return metadata identifying the authorization server and the required audience

#### Scenario: Dynamic client registration
- **WHEN** a DCR-only client posts a registration request to the server's registration endpoint
- **THEN** the server SHALL issue a client registration (client id + stored redirect URIs) without requiring the client to register with CyberdyneAuth directly

#### Scenario: Authorization-code flow bridged to CyberdyneAuth
- **WHEN** a registered client begins an authorization-code + PKCE flow
- **THEN** the server SHALL forward the authorization to CyberdyneAuth, complete the code exchange with the upstream client credentials, and return the resulting user access (and refresh) token to the client

#### Scenario: Token from the flow authorizes tool calls
- **WHEN** a client calls a tool with a bearer token obtained through the OAuth flow
- **THEN** the server SHALL validate it via the existing auth path and authorize the call only if the caller holds the `mnemosyne` entitlement

#### Scenario: Authenticated user lacking entitlement
- **WHEN** a user completes the OAuth login but does not hold the `mnemosyne` entitlement
- **THEN** tool calls SHALL be rejected with a missing-entitlement error

#### Scenario: Existing credentials still accepted
- **WHEN** a client connects with a Mnemosyne API key (`mnem_…`) or a directly supplied CyberdyneAuth bearer token
- **THEN** the server SHALL authenticate it as before, independent of the OAuth flow

#### Scenario: OAuth disabled
- **WHEN** the OAuth feature flag is off
- **THEN** the server SHALL not serve OAuth metadata endpoints and SHALL continue to accept API-key and bearer credentials
