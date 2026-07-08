# Design — one-click MCP OAuth

## Context

MCP clients that offer a zero-config "add this URL" connector (claude.ai, Claude
Desktop) implement the MCP authorization spec: **protected-resource metadata
(RFC 9728) → authorization-server discovery (RFC 8414 / OIDC) → dynamic client
registration (RFC 7591) → authorization-code + PKCE (RFC 7636), with the token
audience bound to the MCP resource (RFC 8707)**.

Observed facts (probed 2026-07-08):

- MCP server serves no OAuth metadata (`/.well-known/oauth-protected-resource` →
  404). Only static-bearer + API-key auth exists.
- CyberdyneAuth OIDC metadata (`/.well-known/openid-configuration`):
  - `authorization_endpoint`, `token_endpoint`, `jwks_uri` present
  - `grant_types_supported`: `authorization_code`, `refresh_token`,
    `client_credentials`
  - `code_challenge_methods_supported`: `S256`
  - **no `registration_endpoint`** → **no DCR**
  - does **not** serve `/.well-known/oauth-authorization-server` (RFC 8414); only
    the OIDC document.
- FastMCP 3.4.3 provides `OAuthProxy`, `RemoteAuthProvider`, `JWTVerifier`,
  `TokenVerifier`, `MultiAuth`.
- **Verified live (2026-07-08):** a CyberdyneAuth **user** access token with
  `aud: None` and no `entitlements` claim in the JWT authorizes the deployed MCP
  (41 tools) — Mnemosyne resolves the `mnemosyne` entitlement via introspection.
  So a *user* token authorizes without any audience binding.

## Decision

Use **FastMCP `OAuthProxy`** on the MCP server, bridging to CyberdyneAuth.

`OAuthProxy` exists precisely for "upstream AS supports auth-code + PKCE but not
DCR." It presents a DCR-compliant OAuth surface to MCP clients (issuing local
client registrations and storing each client's redirect URIs), while using one
fixed upstream client, registered once with CyberdyneAuth, for the actual
authorization. Flow:

```
claude.ai ──DCR──▶ MCP OAuthProxy         (proxy issues a local client_id)
claude.ai ──authorize (PKCE)──▶ MCP OAuthProxy ──▶ CyberdyneAuth /authorize
   user logs in + consents at CyberdyneAuth ──▶ code ──▶ MCP proxy callback
MCP OAuthProxy ──token (code+verifier, upstream client secret)──▶ CyberdyneAuth /token
   ◀── user access+refresh JWT ── returned to claude.ai
claude.ai ──tool call (Bearer JWT)──▶ MCP server ──▶ existing verify() (JWKS/introspection + entitlement)
```

### Why not the alternatives

- **Pure delegation (`RemoteAuthProvider`, point clients straight at
  CyberdyneAuth):** simplest, but requires the client to register with
  CyberdyneAuth — impossible without DCR. Rejected.
- **Mnemosyne as a full authorization server (issue our own end-user tokens):**
  large surface (user auth, consent, key management, token issuance) that
  duplicates CyberdyneAuth and violates "no local credential storage for
  identities." Rejected.

## Token validation & coexistence

- Tokens minted through the proxy are ordinary CyberdyneAuth JWTs. Validation is
  **unchanged**: the existing `auth_port.verify` (API-key path → CyberdyneAuth
  JWKS/introspection) already handles them, and `can_access` still requires the
  `mnemosyne` entitlement/audience. The proxy's job is issuing/obtaining tokens,
  not a new authorization model.
- The MCP server must continue to accept **API keys (`mnem_…`)** and
  directly-supplied bearer tokens. `OAuthProxy` governs the OAuth endpoints and
  the token verifier; the verifier delegates to the existing composite
  (`ApiKeyAuthAdapter` → CyberdyneAuth), so all three credential types resolve a
  `CallerIdentity` the same way. If FastMCP's provider model can't wrap the
  custom `default_authenticate`, use `MultiAuth` to combine the OAuth provider
  with the existing bearer path; the tool-level `caller.can_access` check is
  retained regardless.

## Token authorization (audience not required for the connector)

The one-click connector is inherently a **user** logging in via authorization
code. In CyberdyneAuth, entitlements are **user-only** — a user token authorizes
Mnemosyne through the `mnemosyne` **entitlement** (surfaced via introspection),
not through an audience. This is the exact mechanism the production web app and
manually-minted user tokens already use, and it is **verified live**: a user
token with `aud: None` authorizes the deployed MCP.

Consequently the proxy does **not** need to request `audience=mnemosyne` on the
upstream exchange, and audience binding is **not** a requirement for this change.
(Audience binding matters only for *service* client-credentials tokens, which the
interactive connector does not use.) The proxy may still forward the default
`openid email profile offline_access` scopes for refresh; authorization is decided
by the user's entitlement at tool-call time, unchanged.

## External dependency — CyberdyneAuth client

A confidential client provisioned out-of-band (admin API), not created by this
change's code:

- `client_id`: `mnemosyne-mcp` (or a `cyb_…` id)
- `grant_types`: `[authorization_code, refresh_token]`
- `allowed_audiences`: `["mnemosyne"]`
- `redirect_uris`: the OAuthProxy callback on the public MCP host, e.g.
  `https://mnemosyne.mcp.coolify.cyberdynecorp.ai/auth/callback` (exact path per
  FastMCP)
- scopes: `openid profile email offline_access` (for refresh)

Secret lives only in Coolify env (`MCP_OAUTH_UPSTREAM_CLIENT_SECRET`), never
committed.

## Configuration (new)

- `MCP_OAUTH_ENABLED` (default false — feature-flag the flow)
- `MCP_OAUTH_PUBLIC_BASE_URL` = `https://mnemosyne.mcp.<domain>` (issuer/base the
  proxy advertises)
- `MCP_OAUTH_UPSTREAM_AUTHORIZE_URL` / `_TOKEN_URL` (from CyberdyneAuth OIDC)
- `MCP_OAUTH_UPSTREAM_CLIENT_ID` / `_CLIENT_SECRET`
- `MCP_OAUTH_AUDIENCE` (default `mnemosyne`)
- `FASTMCP_HTTP_ALLOWED_HOSTS` must include the public MCP host (already required).

## Open questions (verify before / during apply)

1. **Auth-code authorization — RESOLVED (verified live 2026-07-08):** a
   CyberdyneAuth user token authorizes the MCP via the `mnemosyne` entitlement
   (introspection) with no audience. The connector produces a user token, so no
   audience binding is needed. Remaining sub-check: confirm the *logged-in user*
   holds the `mnemosyne` entitlement (see #3) — that, not audience, is the gate.
2. **DCR redirect URIs:** claude.ai registers dynamic redirect URIs; confirm
   `OAuthProxy` stores per-client redirect URIs and validates them exactly while
   using its own fixed upstream callback.
3. **User entitlement:** the flow authenticates a *user*; that user must hold the
   `mnemosyne` entitlement or tool calls 403 after a successful login. Document
   this; it is expected behavior, not a bug.
4. **Refresh/expiry:** confirm refresh-token rotation works end-to-end so
   long-lived connectors don't silently break at access-token expiry.
5. **Metadata shape:** confirm whether target clients require the RFC 8414
   `/.well-known/oauth-authorization-server` doc (which the proxy serves for
   itself) versus reading OIDC config; the proxy is the AS from the client's point
   of view, so it serves its own metadata.

## Security

- PKCE (S256) enforced end-to-end.
- Exact redirect-URI matching per registered client; reject others.
- Audience-bound tokens; `mnemosyne` entitlement still required at tool level.
- Client secret and any proxy signing key only in Coolify env.
- Feature-flagged (`MCP_OAUTH_ENABLED`) so it ships dark and is enabled after the
  upstream client + audience behavior are verified in staging.
- No new long-lived credential store beyond the proxy's client-registration
  records (local client_ids + redirect URIs; no end-user secrets).
