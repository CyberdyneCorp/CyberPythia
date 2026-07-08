# Tasks

## 0. Pre-flight verification (design open questions)
- [x] 0.1 ~~Confirm auth-code audience~~ — RESOLVED: verified live that a CyberdyneAuth user token (no audience) authorizes the MCP via the `mnemosyne` entitlement; no audience binding needed
- [ ] 0.2 Confirm `OAuthProxy` in FastMCP 3.4.3 stores per-client redirect URIs and validates them exactly while using a fixed upstream callback
- [ ] 0.3 Confirm refresh-token rotation works end-to-end through the proxy
- [ ] 0.4 Confirm the logged-in user holds the `mnemosyne` entitlement (else tool calls 403 after login — expected)

## 1. CyberdyneAuth client (out-of-band)
- [ ] 1.1 Provision confidential client `mnemosyne-mcp` (`authorization_code` + `refresh_token`, `allowed_audiences: ["mnemosyne"]`, redirect URI = MCP proxy callback); store id/secret in Coolify env only

## 2. Configuration
- [ ] 2.1 Add settings: `mcp_oauth_enabled`, `mcp_oauth_public_base_url`, upstream authorize/token URLs, upstream client id/secret (no audience setting — user tokens authorize via entitlement)
- [ ] 2.2 Ensure `FASTMCP_HTTP_ALLOWED_HOSTS` includes the public MCP host

## 3. MCP server wiring
- [ ] 3.1 Construct a FastMCP `OAuthProxy` (upstream endpoints + client creds + audience) with a `JWTVerifier`/token verifier that delegates to the existing composite auth
- [ ] 3.2 Attach the proxy to the MCP server behind the feature flag; when disabled, keep today's bearer/API-key behavior
- [ ] 3.3 Preserve the tool-level `caller.can_access` entitlement check for all credential types (OAuth token, API key, bearer)

## 4. Deployment
- [ ] 4.1 Add Coolify env vars (compose + deploy doc); redeploy with the flag off, then enable in staging
- [ ] 4.2 Verify metadata endpoints served: `/.well-known/oauth-protected-resource` (and the proxy's AS metadata + registration endpoint)

## 5. Tests
- [ ] 5.1 Unit: OAuth metadata endpoints served only when enabled; absent when disabled
- [ ] 5.2 Unit: a user token authorizes tool calls via the `mnemosyne` entitlement; a user without the entitlement is rejected
- [ ] 5.3 Unit/regression: API-key and direct-bearer credentials still authenticate with OAuth enabled
- [ ] 5.4 Integration/e2e (staging): full connector handshake (DCR → authorize+PKCE → token → tool call) against CyberdyneAuth

## 6. Docs
- [ ] 6.1 Update `docs/mcp-consumers.md` + `docs/auth-integration.md`: one-click connector setup, entitlement requirement, and when to prefer API keys
- [ ] 6.2 Update `docs/deploy-coolify.md` with the new env vars and the `mnemosyne-mcp` client
