# Mnemosyne — GitHub Context & Memory Layer

Mnemosyne turns a GitHub organization into an AI-readable engineering memory.
Agents consume it over **MCP**, humans and services over **REST** and a **Svelte
dashboard** — documentation, OpenSpec changes, issues, pull requests, file
trees, engineering metrics, and task-specific **context packs**, all indexed
from GitHub with read-only credentials and secured by
[CyberdyneAuth](https://github.com/CyberdyneCorp/CyberdyneAuth).

> Mnemosyne gives AI agents the missing memory layer they need to understand
> your GitHub organization.

## Architecture

- **`mnemosyne-backend/`** — Python 3.12 · FastAPI (REST) + FastMCP (agents) +
  arq worker (sync jobs) · hexagonal architecture · SQLAlchemy 2 + Alembic ·
  PostgreSQL + pgvector · Redis · MinIO
- **`mnemosyne-web/`** — SvelteKit 2 · Svelte 5 (runes) · TypeScript · MVVM ·
  `oidc-client-ts` ("Connect with Cyberdyne")
- **Auth** — CyberdyneAuth is the identity plane: OIDC login for the UI,
  client-credentials service tokens for agents, JWKS validation with RFC 7662
  introspection fallback, access gated by the `mnemosyne` entitlement. Agents may
  also authenticate with a **Mnemosyne API key** (`mnem_…`, generated in the UI)
  or connect via **one-click MCP OAuth** (claude.ai / ChatGPT), which bridges to
  CyberdyneAuth — all three credential types work side by side.
- **Spec** — the system is spec-driven; the living capabilities are in
  `openspec/specs/` (auth, mcp-interface, rest-api, web-ui, repository-sync,
  engineering-intelligence, delivery-intelligence, …), with proposed and archived
  changes under `openspec/changes/`.

Services: `mnemosyne-api` (8000) · `mnemosyne-mcp` (8100) · `mnemosyne-worker`
· `mnemosyne-web` (3000) · postgres (host 5433) · redis · minio.

## Quick start

```bash
# 0. Prereqs: uv, just, docker, node 22
just install            # backend deps (uv) + frontend deps (npm)

# 1. Infra (postgres/pgvector on host port 5433, redis, minio)
just docker-up

# 2. Migrate + run the API
just migrate
just dev                # http://localhost:8000 (OpenAPI at /docs)

# 3. In other terminals
just worker             # sync job consumer
just mcp                # MCP server on :8100
cd mnemosyne-web && npm run dev   # dashboard on :5173
```

Copy `.env.example` to `.env` and fill in `TOKEN_ENCRYPTION_KEY`
(`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`),
the CyberdyneAuth client credentials, and optionally `OPENAI_API_KEY`
(without it, semantic search and ask run in a degraded deterministic mode).

## Quality gates

```bash
just quality            # lint (ruff) + typecheck (mypy --strict) + unit coverage ≥ 90%
just test-integration   # real postgres/redis/minio (docker compose)
just test-bdd-local     # boots API+worker+MCP against mock GitHub/auth fixtures
just openspec-validate  # spec artifacts stay valid
```

CI (`.github/workflows/ci.yml`) blocks merge on lint, typecheck, unit coverage
< 90%, integration tests, docker build, and OpenSpec validation.

## Using Mnemosyne

**REST** — bearer token (CyberdyneAuth) on everything except `/api/v1/health`:

```bash
TOKEN=$(curl -s -X POST https://auth.backend.coolify.cyberdynecorp.ai/api/v1/auth/oauth2/token \
  -d grant_type=client_credentials -d client_id=$ID -d client_secret=$SECRET | jq -r .access_token)
curl -H "Authorization: Bearer $TOKEN" https://mnemosyne.../api/v1/repos
```

**MCP** — point an agent at `https://mnemosyne-mcp.../mcp` (streamable HTTP) with a
bearer token, a Mnemosyne **API key** (`mnem_…`), or — for DCR clients like
claude.ai / ChatGPT — the **one-click OAuth** connector (paste the URL, log in).
The suite spans per-repo, whole-portfolio, per-organization, and cross-repo tools —
including global search, stale-triage finders, organization rollups, and
capability / feature-document composites. See
[docs/mcp-consumers.md](docs/mcp-consumers.md).

**Dashboard** — sign in with "Connect with Cyberdyne". Admins register a
GitHub credential — a read-only PAT or a **GitHub App** installation (App
tokens are short-lived and scoped, and drive **webhook-based near-real-time
updates**; see [docs/github-app.md](docs/github-app.md)) — discover
repositories, choose indexing modes
(`docs_only` / `project_intelligence` / `code_metadata` / `code_context` /
`full_context`), and trigger syncs. The `code_context` and `full_context`
modes additionally capture source-code content, chunk it by symbol, and
build a semantic **code search** index (Phase 3).

The **Intelligence** dashboard scores each repository's **health** (0–100 + grade
+ findings) and rolls the org up into a portfolio view — leaderboard, most-active,
abandoned, and bug-heavy repositories — plus delivery/backlog/bottleneck/maintenance
analytics over MCP and REST (Phase 5). For project managers and POs, Phase 5.1 adds
**delivery intelligence** — cycle/lead-time percentiles, aging WIP, throughput and backlog
**forecasting**, work-mix, quality signals, milestone burn-up, and team-load/bus-factor —
on a forward-only metrics time-series; see
[docs/engineering-intelligence.md](docs/engineering-intelligence.md).

The dashboard also filters intelligence **by organization** (server-scoped
leaderboard/scorecard plus an org overview, recent-activity, and stale-triage panels),
surfaces per-repository **Capabilities** with a grounded **feature-document**
generator, and offers a portfolio-wide **Search** page (documentation / code / issues
across all repositories, or fuzzy repo lookup). The same organization rollups,
cross-repo search/stale finders, and capability / feature-document composites are
available to agents over MCP and to services over REST — so PM/PO questions like
"which capabilities does this project have?", "how many bugs?", or "what can my
organization do right now?" resolve in a single call.

## Docs

- [docs/auth-integration.md](docs/auth-integration.md) — CyberdyneAuth setup:
  clients to register, entitlement, env vars
- [docs/mcp-consumers.md](docs/mcp-consumers.md) — the MCP tool suite for agents
- [docs/mnemosyneignore.md](docs/mnemosyneignore.md) — excluding paths from indexing
- [docs/github-app.md](docs/github-app.md) — GitHub App + webhooks (near-real-time sync)
- [docs/engineering-intelligence.md](docs/engineering-intelligence.md) — health scores + portfolio analytics
- [docs/deploy-coolify.md](docs/deploy-coolify.md) — production deployment

## Security model

Read-only GitHub PAT, encrypted at rest (Fernet), never returned by any API.
`.mnemosyneignore` + a global denylist keep sensitive paths out of the index;
secret scanning quarantines documents containing credentials before they are
stored or embedded. Every sensitive or denied operation is audit-logged with
the caller's CyberdyneAuth identity.
