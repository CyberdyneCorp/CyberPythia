# Design — GitHub App manifest onboarding

## Flow

```
[dashboard] admin clicks "Create GitHub App for <org>"
   → backend: GET /api/v1/github/app/manifest?organization=<org>
        returns { post_url, manifest, state }   (state = signed CSRF, stored short-lived)
   → frontend auto-submits a form POST to
        https://github.com/organizations/<org>/settings/apps/new?state=<state>
        with field manifest=<json>
[github] admin reviews + clicks "Create GitHub App"
   → GitHub redirects to manifest.redirect_url:
        GET /api/v1/github/app/manifest-callback?code=<tmp>&state=<state>
   → backend: verify state; POST https://api.github.com/app-manifests/<code>/conversions
        → { id (app_id), pem (private_key), webhook_secret, html_url, slug, ... }
        → persist github_app connection (pending_installation), encrypted
        → 302 to <html_url>/installations/new       (admin installs on the org)
[github] admin selects repositories + Install
   → GitHub redirects to the App "Setup URL" (set in the manifest):
        GET /api/v1/github/app/setup?installation_id=<id>&setup_action=install&state=<state>
   → backend: attach installation_id, mint an installation token to validate,
        mark the connection active
        → 302 to the web /connections page
```

## Key decisions

- **Manifest content** — read-only `contents`, `issues`, `pull_requests`, `metadata`;
  `default_events`: push, issues, issue_comment, pull_request, pull_request_review,
  pull_request_review_comment, repository, installation, installation_repositories;
  `hook_attributes.url` = our webhook endpoint; `redirect_url` = manifest-callback;
  `setup_url` = setup callback; `public: false`. GitHub **generates the webhook secret**
  and returns it in the conversion response — we never invent or display it.
- **Org vs user** — post to
  `https://github.com/organizations/{org}/settings/apps/new` so the App is owned by the
  org; the admin must have org owner rights (GitHub enforces).
- **CSRF / state** — a signed, short-TTL `state` (Redis or signed token) tying the
  callback to the initiating admin + org; both callbacks verify it. Mismatch → 400.
- **Connection lifecycle** — reuse the `github_app` connection kind with a new
  `pending_installation` status between manifest-callback (creds known, no
  installation) and setup (installation_id known → active). Discovery/sync ignore
  pending connections.
- **Idempotency / re-runs** — if setup arrives for an org that already has a pending
  App connection, update it; if an active App connection exists, the setup just
  refreshes the installation_id.
- **Fallback** — the existing `POST /api/v1/github/app/connect` manual form is
  unchanged for environments where the manifest flow is blocked (e.g., no browser
  hand-off).

## Security

- Both callbacks are unauthenticated **GET redirects from GitHub** (like the OAuth
  callback), so they rely on the signed `state` for integrity; the sensitive
  conversion (`code → credentials`) is a server-to-server call. The manifest
  `code` is single-use and expires in ~1 hour.
- Private key + webhook secret are Fernet-encrypted at rest and never returned by any
  API, exactly as the manual path.
- Initiating the manifest (getting `post_url`/`state`) is **admin-only**; the GitHub
  redirects carry no long-term secret, only the one-time `code` / `installation_id`.

## Open questions

1. **State store** — reuse Redis (already present) with a short TTL, or a signed
   stateless token (HMAC of org+admin+expiry)? Leaning signed-stateless to avoid new
   Redis keys and work across instances.
2. **Setup URL vs installation webhook** — capture `installation_id` from the setup
   redirect (primary) and also accept the `installation` **webhook** as a backstop if
   the admin closes the tab before redirect. Confirm GitHub sends both.
3. **App name uniqueness** — GitHub App names are globally unique; the manifest name
   (e.g. `Mnemosyne-CyberdyneCorp`) may collide. Surface GitHub's error and let the
   admin retry with a suffix.
