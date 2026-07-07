# GitHub App + webhooks (Phase 4)

A GitHub App is the production credential model: short-lived, scoped
installation tokens (1 hour) instead of a broad personal PAT, plus webhooks
that keep the index fresh within seconds of a change. PAT connections keep
working; the App is additive.

## 1. Create the GitHub App (once)

GitHub → org **Settings → Developer settings → GitHub Apps → New GitHub App**:

- **Repository permissions** (read-only): Contents, Issues, Pull requests, Metadata.
- **Subscribe to events**: Push, Issues, Issue comment, Pull request, Pull request review,
  Pull request review comment, Repository, Installation, Installation repositories.
- **Webhook**:
  - URL: `https://mnemosyne.backend.<domain>/api/v1/webhooks/github`
  - Secret: generate a strong random string — you'll paste it into Mnemosyne.
  - Active: on.
- **Private key**: after creating the App, **Generate a private key** (downloads a `.pem`).

Note the **App ID** (App settings page). Then **Install** the App on the org and note
the **Installation ID** (the number in the installation settings URL,
`/installations/<id>`).

## 2. Register the installation in Mnemosyne

Dashboard → **GitHub Connection** → *GitHub App* form: paste the App ID, Installation ID,
the private-key PEM, and the webhook secret. Mnemosyne validates by minting an installation
token, then encrypts the private key + webhook secret at rest. Or via API:

```bash
curl -X POST https://mnemosyne.backend.<domain>/api/v1/github/app/connect \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H 'Content-Type: application/json' \
  -d @- <<JSON
{ "app_id": "123456", "installation_id": "99999999",
  "private_key": "-----BEGIN PRIVATE KEY-----\n…\n-----END PRIVATE KEY-----\n",
  "webhook_secret": "the-secret-you-set" }
JSON
```

Then run discovery and enable pilot repositories as usual.

## 3. How updates flow

GitHub delivers each event to `POST /api/v1/webhooks/github`. Mnemosyne:

1. Verifies the `X-Hub-Signature-256` HMAC-SHA256 of the raw body against the installation's
   webhook secret (constant-time). Invalid/missing → **401**, no processing.
2. Dedupes by `X-GitHub-Delivery` (redeliveries are acknowledged, not reprocessed).
3. Dispatches:
   - `push` → enqueue a mode-appropriate sync (idempotent, content-hash-skipping).
   - `issues` / `issue_comment` → upsert that one issue + recompute issue metrics.
   - `pull_request` / `pull_request_review*` → upsert that one PR + recompute PR metrics.
   - `repository` → update metadata (or disable on delete).
   - `installation` / `installation_repositories` → re-discover the installation's repos.
   - Events for non-indexed repositories are acknowledged and ignored.

Watch **GitHub Connection → Webhook activity**, or `GET /api/v1/admin/webhook-deliveries`,
to confirm deliveries are arriving and their outcomes.

## Security

- The webhook endpoint is the only non-health route exempt from CyberdyneAuth bearer
  auth; it is gated solely by HMAC signature validation of the raw body.
- App private key + webhook secret are Fernet-encrypted at rest and never returned by
  any API. Installation tokens are minted on demand, cached in memory until near expiry,
  and never persisted.
- Every delivery is audit-logged (event, action, repository, outcome).

## Env vars

No new required env vars — the App JWT is signed with `PyJWT[crypto]` (already a
dependency). `SOURCE_SIZE_CAP_BYTES` / `CODE_WINDOW_*` from Phase 3 still apply to
webhook-triggered syncs.
