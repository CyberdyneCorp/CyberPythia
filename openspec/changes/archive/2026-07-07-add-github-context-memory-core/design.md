# Design: add-github-context-memory-core

## Context

Greenfield repository. Source product spec: `mnemosyne_github_context_memory_spec.md` (Mnemosyne — AI memory layer for GitHub organizations). Audience is the whole company: agents consume via MCP, humans and services via REST and a Svelte dashboard. Identity is centralized in **CyberdyneAuth** (`https://auth.backend.coolify.cyberdynecorp.ai`), a FastAPI OIDC provider with token introspection (RFC 7662), client-credentials service tokens, entitlements, and an admin console (verified against its live `openapi.json` and `docs/oidc.md` / `docs/oauth-external-clients.md`).

Constraints:
- Read-only GitHub access for the MVP (fine-grained PAT); GitHub App + webhooks deferred.
- Hexagonal architecture on the backend; domain must not import FastAPI/FastMCP/GitHub SDKs/DB drivers.
- `uv` + `just` workflow; unit coverage > 90%; BDD local + staging; Coolify deployment.
- Mnemosyne stores private-repo documentation and metadata — security-critical.

## Reference Implementations

Existing CyberdyneCorp repos solve the same integration problems; consult them before inventing patterns, and prefer staying consistent with them:

- **`CyberdyneCorp/CyberdyneRAG`** — closest architectural sibling: hexagonal FastAPI backend with an embedded FastMCP server, PostgreSQL + pgvector, uv + just, Alembic, Docker Compose. Reference for: backend layout, **CyberdyneAuth verification from a Python service** (`src/cyberdyne_rag/domain/auth/ports.py` and its adapters), FastMCP wiring, pgvector persistence, `justfile`/CI conventions.
- **`CyberdyneCorp/cyberdynedao`** — full-stack app with a Svelte frontend authenticating against CyberdyneAuth. Reference for: **frontend OIDC integration** (`frontend/src/lib/auth/cyberdyneAuthService.ts`), frontend Dockerfile, **Coolify deployment** (`docs/deploy-coolify.md`), backend env-var documentation (`docs/backend-env-vars.md`).
- **`CyberdyneCorp/CyberdyneAuth`** — the auth service itself: `docs/oidc.md`, `docs/oauth-external-clients.md`, `docs/entitlements.md` are normative for the integration; `compose.coolify.yaml` is the house style for Coolify compose files.
- Secondary examples of CyberdyneAuth consumption if more are needed: `CyberDataIngest` (admin UI token store + Coolify deployment doc), `Cyberflies` (openspec change on introspection service tokens), `CyberGeoPy` (Python client-credentials helper).

Divergences from these references should be deliberate and recorded as decisions below.

## Goals / Non-Goals

**Goals:**
- One backend codebase, three runtime services (api, mcp, worker) sharing domain + persistence.
- All access authenticated by CyberdyneAuth and gated by the `mnemosyne` entitlement.
- Docs/OpenSpec/issues/PRs/file-tree indexing with metrics and context packs.
- Deterministic, idempotent, rate-limit-aware sync jobs.

**Non-Goals:**
- Source-code content indexing / semantic code search (later change: `code_context`).
- GitHub App, webhooks, incremental sync (later change).
- Own user database, billing, or multi-tenant SaaS controls beyond entitlements.

## Decisions

### D1. Auth: JWKS-first validation with introspection fallback
Mnemosyne validates CyberdyneAuth RS256 bearer tokens locally against `/.well-known/jwks.json` (cached, refreshed on unknown `kid`). `AUTH_VALIDATION_MODE=introspect` switches to RFC 7662 `POST /api/v1/auth/introspect`, authenticated with Mnemosyne's own client-credentials service token; introspection also serves as fallback when a token validates locally but carries no entitlements claim.
- *Why*: local JWKS keeps per-request latency and CyberdyneAuth load minimal; introspection provides revocation-awareness and the authoritative `entitlements`/`is_admin` claims.
- *Alternatives*: introspect-every-request (simple, authoritative, but adds a network hop and a hard runtime dependency on CyberdyneAuth for every call); cookie sessions (wrong model for MCP/service callers).

### D2. Identity roles from CyberdyneAuth, not local RBAC
Authorization inputs are exactly: `entitlements` (user tokens), `aud` (service tokens), `is_admin`, and optional scopes (`mnemosyne:admin`). No local role tables. Local persistence of identity is limited to `sub` + display snapshot for auditing.
*Verified against the live deployment (2026-07-07):* CyberdyneAuth entitlements are **user-only** (`product_key` or `product_key:plan`, where `product_key` is an OAuth client's `client_id` — the client registry is the product registry); service tokens carry no entitlements, client `allowed_scopes` are registry-validated (arbitrary product keys rejected), so **agents are authorized via `allowed_audiences`** (`aud=mnemosyne`, requested with `audience=` at the token endpoint). Access/service JWTs use `iss: "cyberdyne-auth"` (logical name), not the issuer URL — only OIDC ID tokens use the URL; hence the separate `CYBERDYNEAUTH_TOKEN_ISSUER` setting.
- *Why*: CyberdyneAuth already has groups/policies/entitlements plus an admin console; duplicating RBAC creates drift.
- *Alternative considered*: calling `POST /api/v1/admin/iam/evaluate` per request — rejected for the MVP (admin-scoped API, extra hop); can back a finer-grained policy layer later.

### D3. Three OAuth clients registered in CyberdyneAuth
1. `mnemosyne-web` — public client, `authorization_code` + `refresh_token`, PKCE, scopes `openid email profile offline_access`, `trusted: true`. **Registered: `cyb_W6D9o0J3y1PnHcN4`.**
2. `mnemosyne` — confidential client, `client_credentials`; doubles as the introspection caller and the **product registry entry** (its `client_id` is the entitlement product key). **Registered: `cyb_50UdgxXphi9SJJQX`.**
3. Agent clients — confidential `client_credentials` clients per consuming agent/team with `allowed_audiences: ["mnemosyne"]`. **Demo registered: `cyb_xZMHFyWsRjOwhav3`.**

### D4. Backend layout: single package, hexagonal, three entrypoints
`mnemosyne-backend/app/{domain,application,infrastructure,interfaces}` per the product spec §8. Entrypoints: `interfaces/api` (FastAPI), `interfaces/mcp` (FastMCP over streamable HTTP), `infrastructure/queue/worker.py` (Redis consumer). Domain services (`issue_metrics_service`, `pr_metrics_service`, `context_pack_service`, …) are pure and unit-tested to the 90% floor; adapters are integration-tested.
- *Why FastMCP as separate service*: independent scaling and failure isolation from the REST API; both import the same application use cases.

### D5. Storage roles
- **PostgreSQL + pgvector** — normalized entities (repositories, documents, openspec_changes, issues, pull_requests, source_files, sync_jobs, context_packs, audit_log) plus embeddings (`vector` column on document chunks). Extensions: `vector`, `pg_trgm`, `unaccent`.
- **Redis** — job queue (simple reliable-queue pattern, `LMOVE` + ack), per-repo sync locks, GitHub rate-limit state, context-pack cache keys.
- **MinIO** — raw GitHub payloads (`raw/github/repos/{repo_id}/...`) and context-pack artifacts.
- *Alternative*: Celery/RQ instead of hand-rolled queue — start with `arq` (async, Redis-native, small) rather than Celery's operational surface. (Final pick recorded in tasks; anything satisfying QueuePort is acceptable.)

### D6. GitHub access via a thin async client behind GitHubPort
`httpx`-based client with ETag support, conditional requests, pagination, and rate-limit backoff (sleep-until-reset on 403/429 with `X-RateLimit-Reset`). Raw payloads land in MinIO before normalization (audit + replay). No third-party GitHub SDK in the domain.

### D7. Embeddings: doc-level chunks, provider behind EmbeddingPort
Documents are chunked by markdown section (heading-bounded, ~1–2k tokens) and embedded with `text-embedding-3-small` (configurable). Only docs/OpenSpec content is embedded in this change. Secret scanning (rule-based: key patterns + entropy) runs pre-persist; quarantined docs store metadata only.

### D8. Context packs: hybrid retrieval, no LLM required for the pack itself
`build_context_pack` = semantic search (pgvector) over doc chunks + lexical/label scoring over issues/PRs/OpenSpec + important-file heuristics, assembled deterministically. `ask_repository_question` layers an LLM answer with citations on top of the same retrieval; the LLM never receives content excluded by mode/ignore rules.
- *Why deterministic packs*: testable to the coverage floor, cacheable, cheap; the consuming agent does the reasoning.

### D9. Frontend: SvelteKit 2 + Svelte 5 runes, MVVM, `oidc-client-ts`
Same stack as the CyberdyneAuth admin console (`@cyberdynecorp/svelte-ui-core` where available). `oidc-client-ts` drives the PKCE flow against CyberdyneAuth discovery; viewmodels are rune-based classes; API clients are generated-or-typed thin fetch wrappers.

### D10. Deployment on Coolify
Services: `mnemosyne-api`, `mnemosyne-mcp`, `mnemosyne-worker`, `mnemosyne-web`, `postgres` (pgvector/pgvector:pg16), `redis:7`, `minio`. One Dockerfile for the backend (three commands), one for the web. Secrets via Coolify env: `TOKEN_ENCRYPTION_KEY`, `CYBERDYNEAUTH_ISSUER`, `CYBERDYNEAUTH_CLIENT_ID/SECRET` (backend service client), `OPENAI_API_KEY`. Compose file mirrors CyberdyneAuth's `compose.coolify.yaml` conventions.

## Risks / Trade-offs

- [CyberdyneAuth outage blocks all access] → JWKS cache keeps local validation alive for its TTL; health endpoint distinguishes auth-plane failures; introspection mode degrades to 503 with clear error.
- [Entitlement claim shape drift (introspection `entitlements` format)] → contract test in CI against the live `openapi.json` schema (`IntrospectionResponse`); auth adapter isolates the mapping.
- [GitHub rate limits throttle initial sync of large orgs] → ETag/conditional requests, raw-payload replay from MinIO, per-step resumability, sync scheduling.
- [Secret leakage into embeddings/LLM] → secret scan before persist/embed, `.mnemosyneignore` + global denylist enforced in the sync pipeline (single choke point), quarantine with audit.
- [PAT is org-wide read credential] → encrypted at rest, never returned by API, admin-only management, audit trail; GitHub App in a follow-up change reduces blast radius.
- [90% unit coverage on a heavily-I/O codebase] → hexagonal split keeps domain/application pure; adapters covered by integration tests that don't count against the unit floor (coverage scoped to `domain` + `application` + `interfaces` schemas).
- [MCP auth interop] → FastMCP bearer-token auth uses the same verifier as FastAPI middleware; BDD suite includes an MCP client scenario with a real client-credentials token against staging.

## Migration Plan

Greenfield — no migration. Rollout order:
1. Provision Postgres/Redis/MinIO on Coolify; run Alembic migrations.
2. Register the three OAuth clients + `mnemosyne` entitlement in CyberdyneAuth admin.
3. Deploy api/worker/mcp/web; smoke-test `/api/v1/health`, OIDC login, one MCP tool call.
4. Admin registers the GitHub PAT, enables pilot repositories, runs first syncs.

Rollback: services are stateless; roll back images. DB rollback via Alembic downgrade (pre-GA only).

## Open Questions

- OQ1: Which LLM provider/model backs `ask_repository_question` (answer synthesis)? Default assumption: same provider as embeddings, configurable via env.
- OQ2: Queue library final pick (`arq` assumed) — confirm during task 1.
- ~~OQ3~~ Resolved (2026-07-07): introspection returns `entitlements: ["<product_key>"]` (or `product_key:plan`) for user tokens and `None` + `aud` for service tokens; the adapter maps both and the entitlement gate accepts plan suffixes and service audiences.
- OQ4: MCP transport for company agents (streamable HTTP assumed) — confirm consumers can attach `Authorization` headers.
