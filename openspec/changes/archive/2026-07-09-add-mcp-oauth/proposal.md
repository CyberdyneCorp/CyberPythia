# Add one-click MCP OAuth

## Why

`claude.ai` (and Claude Desktop's native "Add custom connector") authenticate to
a remote MCP server via the **MCP OAuth 2.1 flow**: the client reads the server's
protected-resource metadata, discovers the authorization server, **dynamically
registers itself (RFC 7591 DCR)**, and runs an authorization-code + PKCE flow — no
hand-pasted token. Mnemosyne's MCP server serves none of this today (verified:
`/.well-known/oauth-protected-resource` → 404), so it can only be used with
header-based clients (Claude Code, OpenAI, `mcp-remote`) carrying an API key or a
manually minted bearer.

CyberdyneAuth — our authorization server — supports authorization-code, PKCE
(S256), and refresh tokens, **but does not offer DCR** (`registration_endpoint`
absent from its OIDC metadata). A client that requires DCR therefore cannot
register with CyberdyneAuth directly.

## What changes

- The MCP server gains an **OAuth Proxy** (FastMCP 3.4's `OAuthProxy`) that:
  - serves the client-facing OAuth surface — protected-resource metadata,
    authorization-server metadata, a **DCR endpoint**, and authorize/token
    endpoints — so DCR-only clients can register and connect;
  - bridges to CyberdyneAuth under the hood using a **single pre-registered
    confidential client** (`mnemosyne-mcp`), forwarding the authorization-code +
    PKCE flow to CyberdyneAuth's `authorize`/`token` endpoints.
- Resulting access tokens are **ordinary CyberdyneAuth user JWTs** and are
  validated by the existing auth path (JWKS/introspection + entitlement). No change
  to authorization: a user authorizes via the `mnemosyne` **entitlement**, exactly
  as the web app does today — **verified live**, a user token authorizes the MCP
  with no audience binding. (Audience binding, needed only for service tokens, is
  therefore out of scope.)
- The existing credentials keep working unchanged: **API keys (`mnem_…`)** and
  directly supplied CyberdyneAuth bearer tokens. OAuth is additive.

Non-goals: Mnemosyne becoming a full authorization server / issuing its own
end-user tokens; changing REST API auth (this is MCP-transport only); replacing
API keys (they remain the simplest option for header-based clients).

## Impact

- Affected specs: `mcp-interface` (OAuth connector surface), `auth` (protected
  resource + audience binding).
- Affected code: MCP server auth wiring (`app/interfaces/mcp/server.py`),
  configuration (`app/config.py`) for the OAuth proxy (upstream endpoints, client
  id/secret, public base URL, scopes), composition, Coolify env + allowed-hosts,
  docs.
- External dependency: a new CyberdyneAuth confidential client `mnemosyne-mcp`
  (`grant_types: [authorization_code, refresh_token]`, `allowed_audiences:
  ["mnemosyne"]`, redirect URI = the MCP proxy callback). Provisioned out-of-band.
- Security: introduces an interactive user-consent flow. Mitigations — PKCE
  enforced, exact redirect-URI validation, audience-bound tokens, entitlement
  still required, client secret only in Coolify env, tokens verified via JWKS as
  today. See `design.md` for the open dependencies to verify before implementing.
