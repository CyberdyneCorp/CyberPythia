# CyberdyneAuth integration

Mnemosyne has **no user database**. CyberdyneAuth
(`https://auth.backend.coolify.cyberdynecorp.ai`) is the identity plane; access
is gated by the `mnemosyne` product entitlement (design D1–D3).

## Registered clients (task 3.5 — done 2026-07-07)

| Client | client_id | Notes |
| --- | --- | --- |
| `mnemosyne-web` | `cyb_W6D9o0J3y1PnHcN4` | public, PKCE, trusted; redirect URIs: `http://localhost:5173/auth/callback`, `http://localhost:3000/auth/callback` (add the production callback before deploy) |
| `mnemosyne` | `cyb_50UdgxXphi9SJJQX` | confidential, client-credentials; introspection caller **and** the product registry entry — this client_id **is** the entitlement product key |
| `mnemosyne-agent-demo` | `cyb_xZMHFyWsRjOwhav3` | confidential, client-credentials, `allowed_audiences: ["mnemosyne"]` |

Secrets were shown once at creation and are stored outside the repo
(local `.env` / Coolify secrets). Rotate via
`POST /api/v1/admin/oauth/clients/{client_id}/rotate-secret`.

## Authorization model (verified live)

CyberdyneAuth treats **the OAuth client registry as the product registry**:

- **Users** get entitlement grants
  (`POST /api/v1/admin/entitlements {user_id, product_key}`) where
  `product_key = cyb_50UdgxXphi9SJJQX`. Introspection then returns
  `entitlements: ["cyb_50UdgxXphi9SJJQX"]` (or `…:plan`). Set
  `REQUIRED_ENTITLEMENT=cyb_50UdgxXphi9SJJQX`.
- **Agents/services**: entitlements are user-only and client `allowed_scopes`
  are registry-validated, so agent clients carry
  `allowed_audiences: ["mnemosyne"]` and must request the audience when
  minting: `-d audience=mnemosyne`. Mnemosyne accepts service tokens whose
  `aud` contains `SERVICE_AUDIENCE` (default `mnemosyne`).
- **Admins**: CyberdyneAuth `is_admin` or the `mnemosyne:admin` scope.
- Access/service JWTs carry `iss: "cyberdyne-auth"` (a logical name, unlike
  OIDC ID tokens) — configured via `CYBERDYNEAUTH_TOKEN_ISSUER`.

To onboard a new agent: create a confidential client with
`grant_types: [client_credentials]` and `allowed_audiences: ["mnemosyne"]`;
give the team its client_id/secret.

## How validation works

- `AUTH_VALIDATION_MODE=jwks` (default): RS256 JWTs are verified locally
  against `<issuer>/.well-known/jwks.json` (cached, refreshed on unknown kid).
  If the token carries no `entitlements` claim, Mnemosyne falls back to RFC
  7662 introspection — the authoritative source of `entitlements`/`is_admin`.
- `AUTH_VALIDATION_MODE=introspect`: every request is introspected
  (revocation-aware, adds one auth-plane call per request).

A contract test (`tests/unit/infrastructure/test_introspection_contract.py`)
pins the fields Mnemosyne reads from `IntrospectionResponse`; refresh the
vendored schema fixture when CyberdyneAuth's openapi.json changes.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `CYBERDYNEAUTH_ISSUER` | Base URL; also the JWT `iss` |
| `CYBERDYNEAUTH_CLIENT_ID` / `_SECRET` | backend service client (introspection) |
| `CYBERDYNEAUTH_TOKEN_ISSUER` | `iss` of access/service JWTs (default `cyberdyne-auth`) |
| `AUTH_VALIDATION_MODE` | `jwks` (default) or `introspect` |
| `REQUIRED_ENTITLEMENT` | product key = `cyb_50UdgxXphi9SJJQX` in this deployment |
| `SERVICE_AUDIENCE` | audience accepted from service tokens (default `mnemosyne`) |
| `ADMIN_SCOPE` | defaults to `mnemosyne:admin` |

## Agent quick start

```bash
TOKEN=$(curl -s -X POST $ISSUER/api/v1/auth/oauth2/token \
  -d grant_type=client_credentials -d audience=mnemosyne \
  -d client_id=$AGENT_CLIENT_ID -d client_secret=$AGENT_SECRET | jq -r .access_token)
# REST
curl -H "Authorization: Bearer $TOKEN" https://mnemosyne.../api/v1/repos
# MCP: pass the same token as the bearer auth of your MCP client
```

## Mnemosyne API keys (alternative bearer)

For a long-lived, paste-and-forget credential — instead of hand-minting a
short-lived CyberdyneAuth token — an admin can generate a **Mnemosyne API key**
in the web UI (Connections → API keys) with a configurable expiry (or none).

- Format: `mnem_<secret>`. Only the SHA-256 hash is stored; the plaintext is
  shown **once** at creation.
- Accepted as the bearer on **both REST and MCP** — a bearer beginning with
  `mnem_` is validated against stored keys; any other bearer falls through to
  CyberdyneAuth unchanged.
- Grants the `mnemosyne` entitlement (read/query access) — **not** admin. Admin
  endpoints (connections, org toggles, key management) still require a
  CyberdyneAuth admin token.
- Enforced on expiry; revocable in the UI (`DELETE /api/v1/api-keys/{id}`).

```bash
# Admin creates a key (returns the plaintext once)
KEY=$(curl -s -X POST https://mnemosyne.../api/v1/api-keys \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H 'Content-Type: application/json' \
  -d '{"label":"claude-desktop","expires_in_days":90}' | jq -r .key)
# Agent uses it as the bearer for REST or MCP
curl -H "Authorization: Bearer $KEY" https://mnemosyne.../api/v1/repos
```

Management endpoints (all admin-only): `POST /api/v1/api-keys`,
`GET /api/v1/api-keys` (metadata only — never the plaintext), and
`DELETE /api/v1/api-keys/{id}`.

## One-click MCP OAuth (optional)

When enabled (`MCP_OAUTH_ENABLED`, off by default), the MCP server runs a FastMCP
`OAuthProxy` so DCR-capable clients (claude.ai, Claude Desktop) connect with no
hand-pasted token: the client self-registers, the user logs in against
CyberdyneAuth, and the resulting **user** token authorizes via the `mnemosyne`
entitlement (no audience needed — same as the web app). It bridges to CyberdyneAuth
because CyberdyneAuth supports auth-code + PKCE but not DCR. API-key (`mnem_…`) and
direct-bearer auth remain available on the same server — all three coexist. See
`docs/deploy-coolify.md` for setup.
