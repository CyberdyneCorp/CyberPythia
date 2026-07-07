# Proposal: add-github-app-webhooks

## Why

Today Mnemosyne indexes a repository only when an admin triggers a full sync with a fine-grained PAT. That PAT is a broad, long-lived org-wide credential (flagged as a risk since the core change), and the index drifts out of date between manual syncs. Phase 4 adds the production credential model — a **GitHub App** — and makes the index **self-updating**: GitHub pushes events to Mnemosyne, which reacts to each one with targeted incremental work, so a repository's docs, issues, and PRs stay fresh within seconds of a change instead of until the next manual sync.

A GitHub App also fixes the credential blast radius: installation access tokens are short-lived (1 hour), scoped to only the repositories the org grants the App, and never stored — replacing the personal `gho_` token currently in production.

## What Changes

- **GitHub App authentication** (`GitHubAppAuth`): mint an app JWT (RS256, signed with the App private key) and exchange it for short-lived per-installation access tokens on demand. The App private key and webhook secret are encrypted at rest; installation tokens are cached in memory until near expiry, never persisted.
- **Two credential kinds** on the existing connection model: `pat` (unchanged) and `github_app` (app id, installation id, encrypted private key, encrypted webhook secret). Repository discovery and sync work identically once a token is obtained, so the rest of the pipeline is credential-agnostic.
- **Installation management**: register a GitHub App installation (admin), list the repositories an installation grants, and reconcile them into the repository table.
- **Webhook receiver** (`POST /api/v1/webhooks/github`, unauthenticated but **HMAC-SHA256 signature-gated** with the installation's webhook secret): validates `X-Hub-Signature-256`, dedupes by `X-GitHub-Delivery`, and dispatches events to handlers. Invalid signatures are rejected 401; unknown events acknowledged and ignored.
- **Event-driven incremental sync**:
  - `push` → enqueue a mode-appropriate repository sync for the affected repo (idempotent + content-hash-skip already make this near-real-time and cheap).
  - `issues`, `issue_comment` → upsert the single affected issue.
  - `pull_request`, `pull_request_review`, `pull_request_review_comment` → upsert the single affected PR.
  - `repository` (renamed / archived / deleted / visibility change) → update or remove repository metadata.
  - `installation`, `installation_repositories` → add/remove repositories for the installation.
  - After an incremental issue/PR upsert, recompute that repository's metrics.
- **Webhook delivery audit + idempotency**: each delivery is recorded (delivery id, event, action, repository, outcome); a redelivered id is acknowledged without reprocessing.
- REST additions: `POST /github/app/connect`, `GET /github/app/installations/{id}/repositories`, `POST /webhooks/github`, `GET /admin/webhook-deliveries`.
- Web UI: a GitHub App connection screen (App id, installation id, private key, webhook secret) beside the existing PAT screen, and a webhook-activity panel.
- Alembic migration: connection `kind` + app columns, and a `webhook_deliveries` table.

### Non-goals (future changes)

- GitHub App **user-authorization** OAuth flow (CyberdyneAuth remains the user identity plane; the App is for repository access only).
- Per-path source-diff incremental capture (a `push` triggers a mode-appropriate sync whose content-hash skip already avoids re-embedding unchanged files).
- Automatic GitHub App **creation/registration** via the manifest flow (the App is created once in GitHub's UI; Mnemosyne is given its credentials).
- Webhook dead-letter/replay UI beyond queue-level retry and the delivery log.

## Capabilities

### New Capabilities

- `github-app`: GitHub App authentication (app JWT → installation tokens), installation registration, and installation-repository listing.
- `webhooks`: signature-validated webhook receiver, delivery idempotency/audit, and event-to-incremental-sync dispatch.

### Modified Capabilities

None (additive). Deltas add requirements to existing capabilities without changing current behavior:

- `github-connection`: ADDED — the `github_app` credential kind alongside `pat`.
- `repository-sync`: ADDED — incremental single-issue / single-PR upsert use cases.
- `rest-api`: ADDED — app-connect, installation-repositories, webhook, and delivery-log endpoints.
- `auth`: ADDED — the webhook endpoint is signature-gated, exempt from bearer auth.
- `web-ui`: ADDED — GitHub App connection screen + webhook activity panel.

## Impact

- **Data model**: connection `kind` + nullable app columns (`app_id`, `installation_id`, `encrypted_private_key`, `encrypted_webhook_secret`); new `webhook_deliveries` table. One Alembic migration.
- **Code**: new domain (installation value objects, webhook event model), `GitHubAppPort` + `GitHubAppAuth` adapter, webhook signature verifier, event-dispatch + incremental-sync use cases, webhook router (public), app endpoints, web screens.
- **Dependencies**: none new (`PyJWT[crypto]` and `cryptography` already present for CyberdyneAuth RS256).
- **Security**: expands the attack surface with one public endpoint — mitigated by mandatory HMAC-SHA256 signature validation, delivery-id dedupe, encrypted App secrets, and audit logging. Net security *improvement*: short-lived scoped installation tokens replace the broad personal PAT.
- **Infra**: the App must be created in GitHub (once) and its webhook pointed at `https://mnemosyne.backend.<domain>/api/v1/webhooks/github`; the webhook URL and events are configured in the App settings. No new services.
- **Cost/latency**: webhook-driven syncs replace periodic full syncs, reducing GitHub API and embedding volume overall; a burst of pushes is absorbed by the existing Redis queue with per-repo sync locks.
