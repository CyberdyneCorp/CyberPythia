# Proposal: add-github-context-memory-core

## Why

Technical knowledge at Cyberdyne is fragmented across GitHub repositories — READMEs, `/docs`, OpenSpec folders, issues, pull requests, file trees, and commit history. AI agents, project managers, developers, and business stakeholders lack a single trusted place to ask "how does X work?", "what is the state of project Y?", or "what should an agent read before implementing Z". Mnemosyne turns a GitHub organization (or personal account) into an AI-readable engineering memory, exposed to agents over MCP and to humans and services over REST, secured by the existing CyberdyneAuth identity plane.

## What Changes

- New product: **Mnemosyne** — GitHub context & memory layer (this repo, greenfield).
- Python backend (FastAPI + FastMCP, hexagonal architecture) that:
  - Connects to GitHub with a read-only fine-grained PAT (GitHub App deferred to a later change).
  - Discovers user/organization repositories and lets an operator select which to index.
  - Captures and classifies documentation (README, `/docs`, ARCHITECTURE, SECURITY, CHANGELOG, CONTRIBUTING, ROADMAP) and OpenSpec content (specs, changes, proposals, tasks, designs).
  - Syncs issues and pull requests and computes engineering metrics (resolution time, merge time, time to first review, stale items).
  - Captures repository file trees and detects important manifest/config files (no source-code content indexing in this change).
  - Builds **context packs**: task-specific bundles of relevant docs, OpenSpec changes, issues, PRs, and file paths for agents.
  - Answers repository questions from indexed context (doc-level embeddings via pgvector).
- **CyberdyneAuth integration** (replaces any homegrown auth):
  - Humans sign in to the web UI via "Connect with Cyberdyne" (OIDC authorization-code + PKCE against `https://auth.backend.coolify.cyberdynecorp.ai`).
  - Agents and services authenticate with client-credentials service tokens.
  - Backend validates bearer tokens locally against CyberdyneAuth JWKS (RS256), with RFC 7662 introspection (`/api/v1/auth/introspect`) as fallback/authoritative path.
  - Access gated by CyberdyneAuth entitlements (product `mnemosyne`); admin operations gated by `is_admin`.
- REST API (FastAPI) and MCP server (FastMCP) as separate services sharing the same domain and auth layer.
- Svelte 5 + TypeScript web UI (MVVM) — repository dashboard, docs/OpenSpec viewer, issues/PR analytics, context-pack builder.
- Storage: PostgreSQL + pgvector, Redis (queue/cache/locks), MinIO (raw GitHub payload snapshots).
- Deployment: Docker Compose on Coolify (`mnemosyne-api`, `mnemosyne-mcp`, `mnemosyne-worker`, `mnemosyne-web`, postgres, redis, minio).
- Quality gates: `uv` + `just`, unit coverage > 90%, integration tests, BDD (local + staging), CI blocks merge on lint/typecheck/tests/coverage failure.

### Non-goals (deferred to later changes)

- Source-code content indexing, function/class chunking, semantic code search (`code_context` / `full_context` modes).
- GitHub App installation flow and webhooks / incremental near-real-time sync.
- Multi-tenant SaaS beyond the single Cyberdyne deployment (CyberdyneAuth identities + entitlements are the access model).
- Stripe billing (entitlements are granted via CyberdyneAuth admin).
- Engineering-intelligence dashboards beyond the core metrics listed above.

## Capabilities

### New Capabilities

- `auth`: CyberdyneAuth-backed authentication and authorization for REST, MCP, and web UI — OIDC login, service tokens, JWKS validation, introspection, entitlement gating.
- `github-connection`: Managing GitHub read credentials (fine-grained PAT for MVP) — validation, encryption at rest, permission reporting.
- `repository-sync`: Repository discovery, selection, and sync pipeline — docs capture and classification, OpenSpec capture, issues sync, pull-request sync, file-tree capture, raw payload snapshots.
- `engineering-metrics`: Issue and PR metrics computation (averages, medians, staleness, distributions) per repository.
- `context-packs`: Building task-specific context packs and answering repository questions from indexed context (doc-level semantic search).
- `rest-api`: FastAPI endpoints exposing connection, discovery, sync, docs, OpenSpec, issues, PRs, metrics, ask, and context-pack operations.
- `mcp-interface`: FastMCP server exposing the Mnemosyne tool suite (repository, documentation, issue/PR, metrics, and context tools) to agents.
- `web-ui`: Svelte 5 MVVM dashboard — Cyberdyne login, repository dashboard, repository detail (docs, OpenSpec, issues, PRs, files, metrics), context-pack builder.

### Modified Capabilities

None — greenfield project, no existing specs.

## Impact

- New codebase in this repository: `mnemosyne-backend/` (Python 3.12, FastAPI, FastMCP, SQLAlchemy, Alembic, pgvector) and `mnemosyne-web/` (Svelte 5, TypeScript).
- External dependencies:
  - **CyberdyneAuth** (`https://auth.backend.coolify.cyberdynecorp.ai`): requires registering two OAuth clients — a public authorization-code client for the web UI and confidential/service clients for agents; requires a `mnemosyne` product entitlement to exist; Mnemosyne itself needs a service client to call `/api/v1/auth/introspect`.
  - **GitHub REST API**: read-only fine-grained PAT with Contents, Issues, Pull requests, Metadata read permissions; subject to rate limits.
  - **OpenAI embeddings API** (`text-embedding-3-small`) for doc-level semantic search.
- Infrastructure: new Coolify project with 7 services; secrets for GitHub PAT encryption key, CyberdyneAuth client credentials, embedding API key.
- Security-sensitive: stores encrypted GitHub credentials and private repository metadata/documentation; all access is authenticated and entitlement-gated; secret scanning runs before any content is indexed or embedded.
