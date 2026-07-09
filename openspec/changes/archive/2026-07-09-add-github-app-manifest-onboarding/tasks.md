# Tasks

## 1. Domain / connection lifecycle
- [x] 1.1 Add `pending_installation` to the App connection lifecycle (status on `GitHubConnection`)
- [x] 1.2 `GitHubAppPort.convert_manifest_code(code) -> {app_id, private_key, webhook_secret, html_url, slug}` + GitHub client impl (`POST /app-manifests/{code}/conversions`)

## 2. State / CSRF
- [x] 2.1 Signed short-TTL `state` (org + admin subject + expiry, HMAC) — create + verify helpers

## 3. Application
- [x] 3.1 Use case: build manifest (permissions/events/urls) for an org → manifest + post_url + state
- [x] 3.2 Use case: manifest-callback → convert code → persist pending `github_app` connection → install URL
- [x] 3.3 Use case: setup → attach installation_id → mint token to validate → active

## 4. REST interface
- [x] 4.1 `GET /api/v1/github/app/manifest?organization=` (admin)
- [x] 4.2 `GET /api/v1/github/app/manifest-callback` (state-gated redirect)
- [x] 4.3 `GET /api/v1/github/app/setup` (state-gated redirect → dashboard)

## 5. Web
- [x] 5.1 "Create GitHub App" action per org (fetch manifest, auto-submit form to GitHub)
- [x] 5.2 Handle the return on /connections (refresh connections, surface errors)

## 6. Tests
- [x] 6.1 Unit: manifest generation shape; state sign/verify (valid/expired/tampered)
- [x] 6.2 Unit: manifest-callback (fake conversion) creates pending connection; setup activates it; bad state rejected; non-admin 403
- [x] 6.3 Integration: GitHub client manifest-conversion against a fixture
- [x] 6.4 Web: view-model for create-App + return handling

## 7. Docs
- [x] 7.1 Update `docs/github-app.md` with the one-click manifest path (manual path kept as fallback)
