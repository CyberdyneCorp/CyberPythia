# CyberdyneAuth integration

Mnemosyne has **no user database**. CyberdyneAuth
(`https://auth.backend.coolify.cyberdynecorp.ai`) is the identity plane; access
is gated by the `mnemosyne` product entitlement (design D1–D3).

## One-time setup in CyberdyneAuth (task 3.5)

Register in the admin console (sidebar → Applications) or via
`POST /api/v1/admin/oauth/clients`:

1. **`mnemosyne-web`** — public client for the dashboard
   - `client_type: public`, `grant_types: [authorization_code, refresh_token]`
   - `redirect_uris: ["https://mnemosyne.<domain>/auth/callback", "http://localhost:5173/auth/callback"]`
   - `allowed_scopes: [openid, email, profile, offline_access]`, `trusted: true`
2. **`mnemosyne-backend`** — confidential client, `grant_types: [client_credentials]`.
   Used only to authenticate Mnemosyne's calls to `POST /api/v1/auth/introspect`.
   Store the secret as `CYBERDYNEAUTH_CLIENT_SECRET`.
3. **One confidential client per consuming agent/team** with
   `grant_types: [client_credentials]`.

Then create the **`mnemosyne` entitlement/product** and grant it to every
user and agent client that may access Mnemosyne. Admin rights come from
CyberdyneAuth `is_admin` or the `mnemosyne:admin` scope.

Record the client ids here after registration:

| Client | client_id | Notes |
| --- | --- | --- |
| Web UI | `mnemosyne-web` (expected) | public, PKCE |
| Backend | `mnemosyne-backend` (expected) | introspection caller |
| Agents | one per team | client-credentials |

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
| `AUTH_VALIDATION_MODE` | `jwks` (default) or `introspect` |
| `REQUIRED_ENTITLEMENT` | defaults to `mnemosyne` |
| `ADMIN_SCOPE` | defaults to `mnemosyne:admin` |

## Agent quick start

```bash
TOKEN=$(curl -s -X POST $ISSUER/api/v1/auth/oauth2/token \
  -d grant_type=client_credentials \
  -d client_id=$AGENT_CLIENT_ID -d client_secret=$AGENT_SECRET | jq -r .access_token)
# REST
curl -H "Authorization: Bearer $TOKEN" https://mnemosyne.../api/v1/repos
# MCP: pass the same token as the bearer auth of your MCP client
```
