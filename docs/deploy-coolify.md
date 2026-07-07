# Deploying Mnemosyne on Coolify

Follows the house conventions from cyberdynedao `docs/deploy-coolify.md` and
CyberdyneAuth `compose.coolify.yaml`.

## 1. Create the resource

Coolify → New Resource → **Docker Compose** → this repository, compose file
`compose.coolify.yaml`.

## 2. Environment variables

| Variable | Value | Secret |
| --- | --- | --- |
| `POSTGRES_PASSWORD` | strong random | 🔒 |
| `MINIO_ROOT_PASSWORD` | strong random | 🔒 |
| `TOKEN_ENCRYPTION_KEY` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` | 🔒 |
| `CYBERDYNEAUTH_ISSUER` | `https://auth.backend.coolify.cyberdynecorp.ai` | |
| `CYBERDYNEAUTH_CLIENT_ID` | backend service client id | |
| `CYBERDYNEAUTH_CLIENT_SECRET` | its secret | 🔒 |
| `OPENAI_API_KEY` | embeddings + ask (optional → degraded mode) | 🔒 |
| `PUBLIC_API_BASE_URL` | `https://mnemosyne.backend.<domain>` | |
| `PUBLIC_AUTH_CLIENT_ID` | `mnemosyne-web` | |

## 3. Domains

| Service | Port | Domain |
| --- | --- | --- |
| `mnemosyne-api` | 8000 | `mnemosyne.backend.<domain>` |
| `mnemosyne-mcp` | 8100 | `mnemosyne.mcp.<domain>` — set the domain **with the port** (`https://mnemosyne.mcp.<domain>:8100`) so Coolify routes to container port 8100 instead of the image's first exposed port |
| `mnemosyne-web` | 3000 | `mnemosyne.<domain>` |

If the MCP domain differs from the default, also set
`FASTMCP_HTTP_ALLOWED_HOSTS='["mnemosyne.mcp.<domain>"]'` — FastMCP's
DNS-rebinding protection returns 421 for Host headers not on the allowlist.

The API container runs `alembic upgrade head` on boot.

## 4. Rollout order (design: Migration Plan)

1. Deploy; wait until `GET /api/v1/health` returns `"status": "ok"`.
2. Register the OAuth clients + `mnemosyne` entitlement in CyberdyneAuth
   ([auth-integration.md](auth-integration.md)); update the web client's
   `redirect_uris` with the production callback URL.
3. Sign in to the dashboard as an admin, register the read-only GitHub PAT,
   run discovery, enable pilot repositories, trigger the first syncs.
4. Run the staging BDD suite:

   ```bash
   STAGING_AUTH_ISSUER=https://auth.backend.coolify.cyberdynecorp.ai \
   STAGING_AUTH_CLIENT_ID=<bdd-client> \
   STAGING_AUTH_CLIENT_SECRET=<secret> \
   STAGING_MCP_URL=https://mnemosyne-mcp.<domain> \
   just test-bdd-staging   # STAGING_SERVER_URL=https://mnemosyne.backend.<domain>
   ```

Rollback: services are stateless — redeploy the previous image. Database
rollback via `alembic downgrade` (pre-GA only).
