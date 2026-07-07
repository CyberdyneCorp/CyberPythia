# Tasks: add-github-context-memory-core

> Before each workstream, check the reference implementations listed in `design.md` → *Reference Implementations* (CyberdyneRAG for backend/MCP/pgvector patterns, cyberdynedao for Svelte auth + Coolify, CyberdyneAuth docs for the auth contract). Reuse their patterns unless a design decision says otherwise.

## 1. Project scaffolding & tooling

- [ ] 1.1 Scaffold `mnemosyne-backend/` (uv, `pyproject.toml`, Python 3.12, ruff, mypy strict, pytest + coverage config scoped to `app/domain`, `app/application`, `app/interfaces`)
- [ ] 1.2 Scaffold hexagonal package layout (`app/{domain,application,infrastructure,interfaces}`) per design D4
- [ ] 1.3 Add `justfile` (install, dev, mcp, worker, test, test-unit, test-integration, test-bdd-local, test-bdd-staging, coverage, lint, format, typecheck, quality, docker-up/down, migrate, revision)
- [ ] 1.4 Docker Compose for local dev (postgres/pgvector, redis, minio) + backend Dockerfile with api/mcp/worker commands
- [ ] 1.5 CI workflow: uv sync → lint → typecheck → unit → integration → coverage ≥ 90% → docker build → `openspec validate --all --strict`

## 2. Domain & persistence foundation

- [ ] 2.1 Domain entities and value objects (Repository, Document, OpenSpecChange, Issue, PullRequest, SourceFile, SyncJob, ContextPack; states, document types, indexing modes) with unit tests
- [ ] 2.2 Ports: GitHubPort, RepositoryPort, DocumentPort, IssuePort, PullRequestPort, FilePort, EmbeddingPort, ObjectStoragePort, QueuePort, AuthPort (token verification), AuditPort
- [ ] 2.3 SQLAlchemy models + Alembic baseline migration (incl. pgvector column, `vector`/`pg_trgm`/`unaccent` extensions, audit_log)
- [ ] 2.4 Postgres adapter repositories + integration tests (real Postgres via compose)
- [ ] 2.5 Redis queue adapter (arq or equivalent satisfying QueuePort) + per-repo sync lock + integration tests
- [ ] 2.6 MinIO object-storage adapter + integration tests

## 3. Auth (CyberdyneAuth integration)

- [ ] 3.1 Auth adapter: JWKS fetch/cache, RS256 JWT verification (iss/exp/kid), identity mapping (`sub`, `scope`, `is_admin`, `entitlements`) with unit tests — start from CyberdyneRAG's auth port/adapter (`src/cyberdyne_rag/domain/auth/`)
- [ ] 3.2 Introspection adapter: client-credentials token acquisition for `mnemosyne-backend` + RFC 7662 call, `AUTH_VALIDATION_MODE` switch, contract test against `IntrospectionResponse` schema
- [ ] 3.3 FastAPI auth middleware/dependency: bearer extraction, entitlement gate (`mnemosyne`), admin gate (`is_admin` / `mnemosyne:admin`), consistent 401/403 error shape
- [ ] 3.4 Audit logging for sensitive + denied operations (AuditPort → Postgres) with unit tests
- [ ] 3.5 Register OAuth clients + `mnemosyne` entitlement in CyberdyneAuth (ops task; record client ids in deployment docs)

## 4. GitHub connection & sync pipeline

- [ ] 4.1 GitHub async client (httpx): auth, pagination, ETags, rate-limit backoff; raw payload capture to MinIO; integration tests with recorded fixtures
- [ ] 4.2 Token encryption service (`TOKEN_ENCRYPTION_KEY`, Fernet/AES-GCM) + credential lifecycle use cases (connect/validate/test/rotate/delete) with unit tests
- [ ] 4.3 DiscoverRepositories use case + repository selection/mode (`docs_only` / `project_intelligence` / `code_metadata`)
- [ ] 4.4 Markdown/doc capture: fetch, classify (README/DOCS/OPENSPEC/... per spec), content-hash dedupe; unit tests for classifier
- [ ] 4.5 OpenSpec parser: detect `openspec/`, `specs/`, `changes/`; extract change id, proposal/design/tasks, affected specs, status; unit tests on fixture repos
- [ ] 4.6 Issues sync (fields + resolution time; excludes PRs) with unit tests
- [ ] 4.7 Pull request sync (fields + time-to-merge, time-to-first-review) with unit tests
- [ ] 4.8 File-tree capture + important-file detection (mode `code_metadata`) with unit tests
- [ ] 4.9 `.mnemosyneignore` + global denylist enforcement and secret scanner (pattern + entropy) with quarantine; unit tests
- [ ] 4.10 SyncRepository orchestrator use case: step sequencing, per-step status/progress, idempotency, lock, failure recording; worker wiring; integration test syncing a fixture repository end-to-end

## 5. Metrics & context packs

- [ ] 5.1 IssueMetricsService (avg/median resolution, open-age, stale, by-label/assignee; absent-not-zero rules) — unit tests
- [ ] 5.2 PrMetricsService (avg/median merge time, time-to-first-review, merge rate, size buckets, stale) — unit tests
- [ ] 5.3 Metrics recompute on sync completion + persisted summary with provenance timestamp
- [ ] 5.4 Embedding adapter (OpenAI `text-embedding-3-small` behind EmbeddingPort) + markdown section chunker + pgvector store; integration tests
- [ ] 5.5 Semantic doc search use case
- [ ] 5.6 BuildContextPack use case (hybrid retrieval per design D8, mode constraints, persistence + cache keyed on repo/query/mode/sync-timestamp) — unit tests
- [ ] 5.7 AskRepositoryQuestion use case (grounded answer + citations, insufficient-context behavior) — unit tests with mocked LLM port

## 6. REST API

- [ ] 6.1 FastAPI app: routers for github, repos, docs, openspec, issues, pull-requests, files, metrics, search, ask, context-pack, health per rest-api spec
- [ ] 6.2 Pagination, filtering, consistent error model (code/message/correlation id), status-code mapping incl. 409 sync conflict
- [ ] 6.3 Request/response schemas + OpenAPI security annotations
- [ ] 6.4 Interface tests for every endpoint (authn/authz matrix: no token / valid non-entitled / entitled / admin)

## 7. MCP interface

- [ ] 7.1 FastMCP server (streamable HTTP) with CyberdyneAuth bearer verification reusing the auth adapter
- [ ] 7.2 Repository + documentation tools (`mnemosyne_list_repositories`, `mnemosyne_get_repository_summary`, `mnemosyne_get_repository_tree`, `mnemosyne_get_readme`, `mnemosyne_get_docs_index`, `mnemosyne_search_docs`, `mnemosyne_get_openspec_context`)
- [ ] 7.3 Issue/PR/metrics tools (`mnemosyne_list_issues`, `mnemosyne_get_issue`, `mnemosyne_search_issues`, `mnemosyne_get_issue_resolution_metrics`, `mnemosyne_list_pull_requests`, `mnemosyne_get_pull_request`, `mnemosyne_get_pr_review_metrics`, `mnemosyne_find_stale_issues`, `mnemosyne_find_stale_prs`)
- [ ] 7.4 Context tools (`mnemosyne_build_context_pack`, `mnemosyne_answer_from_repo_context`) + structured tool errors
- [ ] 7.5 MCP interface tests (tool listing, auth rejection, happy-path calls against seeded DB)

## 8. Web UI

- [ ] 8.1 Scaffold `mnemosyne-web/` (SvelteKit 2, Svelte 5, TypeScript, MVVM folders: api/models/viewmodels/views/components; `@cyberdynecorp/svelte-ui-core` when available)
- [ ] 8.2 OIDC login with `oidc-client-ts` (PKCE, refresh rotation, 401-retry, sign-out); access-denied screen for unentitled users — reference cyberdynedao's `frontend/src/lib/auth/cyberdyneAuthService.ts`
- [ ] 8.3 Admin GitHub connection screen (PAT registration, permission display, test, discovery trigger)
- [ ] 8.4 Repository dashboard (cards, enable/mode controls, sync trigger + live status)
- [ ] 8.5 Repository detail tabs (Overview, Documentation, OpenSpec, Issues, Pull Requests, Files, Metrics, Agent Context)
- [ ] 8.6 Context-pack builder + ask view with clickable citations
- [ ] 8.7 Frontend unit tests for viewmodels; web Dockerfile

## 9. BDD & deployment

- [ ] 9.1 BDD suite (pytest-bdd + httpx) against local server: repository sync, documentation ingestion, issue metrics, PR metrics, context-pack generation, MCP tools features
- [ ] 9.2 BDD staging profile (`--server-url` / `STAGING_SERVER_URL`) incl. real CyberdyneAuth client-credentials token acquisition
- [ ] 9.3 Coolify deployment: `compose.coolify.yaml` for the 7 services, env/secret documentation, health checks — follow cyberdynedao `docs/deploy-coolify.md` and CyberdyneAuth `compose.coolify.yaml` conventions
- [ ] 9.4 Deploy to staging; run rollout order from design (clients, entitlement, PAT, pilot repos); execute staging BDD
- [ ] 9.5 README + `docs/` (setup, auth integration guide, MCP consumer guide, `.mnemosyneignore` reference)
