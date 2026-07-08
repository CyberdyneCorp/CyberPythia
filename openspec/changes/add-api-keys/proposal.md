# Add Mnemosyne API keys

## Why

Today the only bearer credential Mnemosyne accepts is a CyberdyneAuth token — a
user login token (short-lived, needs a password) or an agent client-credentials
token (short-lived, needs a client secret and a token endpoint round-trip). To
wire the MCP server (or REST API) into a Claude / OpenAI agent, the operator has
to hand-mint a token that expires in minutes and re-mint it constantly. There is
no "generate a credential, paste it into the connection string, forget about it"
path — which is exactly what an MCP `Authorization` header wants.

## What changes

- Mnemosyne issues its **own** API keys (`mnem_<secret>`), created by an admin in
  the web UI with a **configurable expiry** (or no expiry) and a human label.
- The auth layer accepts an `mnem_`-prefixed bearer as an alternative credential
  for **both MCP and REST**: a matching, non-revoked, non-expired key resolves to
  a caller that carries the `mnemosyne` entitlement (read/query access) — **not**
  admin. Any other bearer falls through to the existing CyberdyneAuth validation
  unchanged.
- Keys are stored **hashed** (SHA-256); the plaintext is shown **once** on
  creation and never again. Keys can be **revoked** and are enforced on expiry.
- New admin-only REST endpoints manage keys; a new web UI panel generates, lists,
  copies (once), and revokes them.

Non-goals: full MCP OAuth 2.1 (discovery + dynamic client registration) for
claude.ai one-click connectors; per-key scoping beyond read/query; per-user
self-service key management (management is admin-only).

## Impact

- Affected specs: `auth` (new alternative credential), `rest-api` (key management
  endpoints), `web-ui` (key management panel).
- Affected code: new `api_keys` table + migration `0007`; `ApiKeyAuthAdapter`
  wrapping `CyberdyneAuthAdapter` in the composition root; domain entity + port +
  Postgres adapter; application use cases; REST router + schemas; SvelteKit
  Connections page section + view model + API client.
- Security: introduces a new long-lived credential. Mitigations — hashed at rest,
  shown once, admin-only issuance, configurable/enforced expiry, revocable, grants
  read/query entitlement only (no admin), every issue/revoke audited.
