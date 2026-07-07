# Design: add-github-app-webhooks

## Context

Builds on the shipped core + Phase 3 changes (deployed, verified on real data). The sync pipeline, connection model, GitHub client, Redis/arq queue with per-repo locks, metrics services, REST/MCP interfaces, and Svelte UI all exist. Phase 4 adds the GitHub App credential kind and a webhook-driven incremental path on top, keeping the domain pure and reusing the existing sync machinery.

Constraints unchanged: hexagonal, `uv`/`just`, unit coverage > 90%, security-critical (a new public endpoint + App secrets). `PyJWT[crypto]` and `cryptography` are already dependencies (CyberdyneAuth RS256), so App JWT signing needs nothing new.

## Goals / Non-Goals

**Goals**
- GitHub App auth (app JWT → short-lived installation tokens) as a credential kind, transparent to the rest of the pipeline.
- Signature-validated webhook receiver with delivery idempotency + audit.
- Event-driven incremental sync (push/issues/PR/repository/installation) reusing existing sync + metrics.
- Short-lived scoped tokens replace the broad personal PAT in production.

**Non-Goals**
- App user-authorization OAuth (CyberdyneAuth stays the user identity plane).
- Per-path source diffing (push triggers a hash-skipping sync).
- Manifest-based App creation; webhook replay UI.

## Decisions

### D1. Credential kind on the existing connection, not a new aggregate
`GitHubConnection` gains `kind: "pat" | "github_app"` and nullable App fields (`app_id`, `installation_id`, `encrypted_private_key`, `encrypted_webhook_secret`). A `CredentialResolver` maps any connection to a usable token: PAT connections decrypt their token (unchanged); App connections call `GitHubAppAuth.installation_token(...)`. Everything downstream (`connection_use_cases.credential_for`, discovery, sync) calls the resolver and stays credential-agnostic.
- *Why not a separate installations table*: reuses the connection lifecycle, repository FK, discovery, and admin surface already built; one migration adds columns + a deliveries table.

### D2. GitHubAppAuth: JWT → installation token, in-memory cache
`GitHubAppAuth` (infra, behind `GitHubAppPort`): builds an RS256 JWT (`iss`=app_id, `iat`/`exp` ~9 min, 60 s clock skew) signed with the App private key, then `POST /app/installations/{id}/access_tokens` with the JWT to get a `{token, expires_at}` (1 h). Tokens are cached per installation in memory until 60 s before expiry. Private key + webhook secret decrypted via the existing `TokenEncryption` (Fernet) only in-process. No token or key persisted beyond the encrypted columns.

### D3. Webhook endpoint: public, HMAC-gated, enqueue-fast
`POST /api/v1/webhooks/github` is registered outside the bearer-auth dependency (the only non-health exemption, per the auth delta). It reads the raw body, computes `hmac.new(secret, body, sha256)`, and `hmac.compare_digest`s against `X-Hub-Signature-256`. Which secret? The delivery carries the installation id (`payload.installation.id`); the receiver looks up the `github_app` connection by installation id to get its webhook secret. Deliveries are deduped by `X-GitHub-Delivery` in a `webhook_deliveries` table before dispatch. Handlers that do real work (sync, single-entity fetch) run through the use-case layer; heavy work (`push` sync) is enqueued on the existing arq queue so the endpoint returns 2xx promptly.
- *Signature-first*: the body is read and verified before any parsing, and comparison is constant-time.

### D4. Event dispatch reuses existing sync + adds two incremental use cases
A pure `WebhookEventRouter` maps `(event, action)` to an intent; a `ProcessWebhookDelivery` use case executes it:
- `push` → `RepositoryUseCases.trigger_sync` (already idempotent, lock-guarded, hash-skipping).
- `issues`/`issue_comment` → new `SyncSingleIssue` use case (fetch one issue via `GitHubPort.get_issue`, upsert, recompute issue metrics).
- `pull_request`/`pull_request_review*` → new `SyncSinglePullRequest` (fetch one PR + its reviews, upsert, recompute PR metrics).
- `repository` → update metadata or disable/remove on delete.
- `installation`/`installation_repositories` → reconcile repositories for the installation.
- Events for non-enabled repositories are acknowledged and dropped.
`GitHubPort` gains `get_issue(token, full_name, number)` and `get_pull_request(token, full_name, number)` (single-entity fetches) with the same normalization as the list methods.

### D5. Metrics recompute extracted for reuse
The metrics computation currently inside the sync orchestrator's `_sync_metrics` step is extracted into a `MetricsRecomputeService` (pure orchestration over the existing `IssueMetricsService`/`PrMetricsService` + summary) so both the full sync and the incremental single-entity syncs recompute identically. No behavior change to full sync.

### D6. Web UI: extend the connection screen, add a deliveries panel
The existing connection screen gains a tab/section for the App kind (app id, installation id, private key textarea, webhook secret) and a read-only webhook-activity list backed by `/admin/webhook-deliveries`. Reuses the existing ConnectionsViewModel patterns.

## Risks / Trade-offs

- [Forged webhooks] → mandatory HMAC-SHA256 over the raw body with `compare_digest`; unknown/mismatched installation → 401. No processing before verification.
- [Replay/duplicate deliveries] → dedupe by `X-GitHub-Delivery`; idempotent upserts and lock-guarded syncs make reprocessing harmless anyway.
- [Webhook storms (mono-repo push floods)] → `push` only enqueues; the per-repo sync lock coalesces concurrent syncs; single-entity handlers are cheap.
- [App private key exposure] → encrypted at rest (Fernet), decrypted only in-process, never returned by any API; short-lived installation tokens limit blast radius vs. the PAT.
- [Clock skew on app JWT] → 60 s `iat` backdating and short `exp`, per GitHub guidance.
- [Endpoint must stay fast] → verify + dedupe + enqueue; only single-entity fetches run inline, bounded to one issue/PR.
- [Coverage on I/O-heavy webhook code] → keep signature verify, event router, dedupe, and dispatch decisions pure/unit-tested; the HTTP adapter and GitHub calls are integration-tested.

## Migration Plan

Additive, backward-compatible. Deploy order:
1. Alembic migration (connection `kind` defaults `pat` + nullable app columns; `webhook_deliveries` table) — safe on the running DB; existing rows become `kind=pat`.
2. Deploy backend/mcp/worker/web.
3. Create the GitHub App in GitHub (once): permissions Contents/Issues/PRs/Metadata read, subscribe to push/issues/issue_comment/pull_request/pull_request_review/pull_request_review_comment/repository/installation events, webhook URL `https://mnemosyne.backend.<domain>/api/v1/webhooks/github`, generate a private key + webhook secret. Install it on the org.
4. Register the installation in Mnemosyne (admin App-connect), run discovery, enable pilot repos.
5. Push a change / open an issue and confirm the delivery log shows it and the index updates.
Rollback: revert images; `alembic downgrade` drops the columns/table (pre-GA only). PAT connections keep working throughout.

## Open Questions

- OQ1: Multiple installations/secrets — v1 looks up the webhook secret by `payload.installation.id`; confirm all events carry `installation.id` (they do for App-delivered events).
- OQ2: Should `push` do a targeted docs/source refresh instead of a full mode sync? v1 enqueues a full (hash-skipping) sync for simplicity; revisit if push latency/cost matters on large repos.
- OQ3: Retention/pruning of `webhook_deliveries` — v1 keeps all; add a TTL/prune job later if volume warrants.
