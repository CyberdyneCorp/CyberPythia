# Tasks: add-github-app-webhooks

> Builds on the shipped core + Phase 3. Reuse the sync pipeline, connection lifecycle, queue + per-repo lock, metrics services, router/error-model, MCP patterns, and Svelte connection screen. Keep the domain pure; unit coverage > 90%. Reference CyberdyneAuth `routers/webhooks.py` for the signature-validation shape.

## 1. Domain: credential kinds, webhook model, single-entity fetch

- [x] 1.1 `ConnectionKind` value object (`pat` | `github_app`); `GitHubConnection` gains `kind` + nullable app fields (`app_id`, `installation_id`, `encrypted_private_key`, `encrypted_webhook_secret`). Unit tests.
- [x] 1.2 Webhook event model: `WebhookEvent` (delivery_id, event, action, installation_id, repository_full_name, payload) + `WebhookIntent` enum; pure `WebhookEventRouter.route(event, action, payload) -> intent`. Unit tests for the full event→intent matrix incl. unknown/ignored.
- [x] 1.3 `GitHubPort` gains `get_issue` and `get_pull_request` (single-entity) returning the same shapes as the list methods.
- [x] 1.4 Webhook signature verifier (HMAC-SHA256 over raw body, constant-time). Unit tests: valid, invalid, missing, tampered body.

## 2. GitHub App auth

- [x] 2.1 `GitHubAppPort` + `GitHubAppAuth` adapter: RS256 app JWT (iss=app_id, iat backdate 60s, short exp), exchange for installation token, in-memory cache until near expiry. Unit tests (fake key + respx for the token endpoint), incl. cache reuse + refresh.
- [x] 2.2 `CredentialResolver`: connection → token (PAT decrypt vs App installation token); connect/validate/list for `github_app` connections (mint token to validate, encrypt private key + webhook secret). Unit tests.
- [x] 2.3 Single-entity GitHub client methods (`get_issue`, `get_pull_request`) with recorded-fixture integration tests.

## 3. Persistence

- [x] 3.1 SQLAlchemy: connection `kind` + app columns; `WebhookDeliveryRow`; `WebhookDeliveryPort`. Alembic migration `0003` (columns default `pat`, deliveries table + delivery-id unique index). Verify on real Postgres.
- [x] 3.2 Connection adapter reads/writes the new columns; `WebhookDeliveryPort` Postgres adapter (record, exists-by-delivery-id, list recent) + integration tests.

## 4. Incremental sync + metrics reuse

- [ ] 4.1 Extract `MetricsRecomputeService` from the sync orchestrator's metrics step (no behavior change); full sync uses it. Unit tests for parity.
- [ ] 4.2 `SyncSingleIssue` + `SyncSinglePullRequest` use cases (enabled-repo guard, single fetch, upsert, metrics recompute). Unit tests.
- [ ] 4.3 Installation-repository discovery reconcile (preserve selection) for App connections. Unit tests.

## 5. Webhook processing

- [ ] 5.1 `ProcessWebhookDelivery` use case: dedupe by delivery id, resolve installation secret, dispatch per intent (push→enqueue sync; issue/PR→single-entity sync; repository→metadata/remove; installation→reconcile), record delivery + audit, ignore non-enabled/unknown. Unit tests for every branch incl. dedupe + non-enabled drop.
- [ ] 5.2 Wire everything in the composition root (app auth, resolver, single-entity use cases, delivery port, webhook processor).

## 6. REST API

- [ ] 6.1 Public webhook router `POST /api/v1/webhooks/github` (raw-body signature verify, fast 2xx/401), registered outside bearer auth. Admin `POST /github/app/connect`, `GET /github/app/installations/{id}/repos`, `GET /admin/webhook-deliveries`. Schemas + OpenAPI security (admin bearer; webhook none).
- [ ] 6.2 Interface tests: webhook valid-signature 2xx + dispatch, invalid/missing-signature 401, redelivery idempotent, app-connect admin-gated, deliveries list; OpenAPI contract for the four paths.

## 7. Web UI

- [ ] 7.1 GitHub App connection form (app id, installation id, private key, webhook secret; masked) + discovery trigger; webhook activity panel from `/admin/webhook-deliveries`. API client + viewmodel additions.
- [ ] 7.2 Viewmodel unit tests; build/check green.

## 8. Docs, deploy, verification

- [ ] 8.1 Docs: GitHub App setup (create App, permissions, events, webhook URL, private key + secret), App-connect flow, security note on the public endpoint; env vars. Update auth-integration / README.
- [ ] 8.2 Full gate (ruff, mypy --strict, unit ≥ 90%, integration, BDD) + `openspec validate --all --strict`; deploy migration `0003` + code; create + install the GitHub App, register the installation, enable a pilot repo, push a change / open an issue, and verify the delivery log + index update end-to-end (and that PAT connections still work).
