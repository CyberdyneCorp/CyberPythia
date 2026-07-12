# Harden the web UI against stored XSS and add security headers

## Why

The SvelteKit web UI renders GitHub-derived Markdown (README/docs captured from
monitored repositories) via `marked.parse()` straight into `{@html}` with no
sanitizer. `marked` ^15 dropped its built-in `sanitize` option, so the raw HTML
is trusted. Anyone with push access to any monitored repository can plant an
`<img onerror=...>` (or a `javascript:` link) that runs in the operator's session
and exfiltrates the OIDC access and refresh tokens held in `localStorage`
(stored XSS, CWE-79, finding #55).

The app also ships no HTTP security headers — no Content-Security-Policy, no
`X-Frame-Options`/`frame-ancestors`, no HSTS, no `X-Content-Type-Options`
(CWE-1021, finding #58). There is no defence-in-depth backstop for an injected
script and the app can be framed for clickjacking.

## What changes

- Sanitize every rendered Markdown string with DOMPurify before it reaches
  `{@html}`. Rendering is centralised in `renderMarkdown()`
  (`src/lib/markdown.ts`), which the `DocumentViewer` component consumes.
  DOMPurify is isomorphic so it is safe under SSR and in the browser.
- Add a strict Content-Security-Policy via `kit.csp` (mode `auto`, nonce-based):
  `default-src 'self'`, `script-src 'self'` (no `unsafe-inline`),
  `object-src 'none'`, `base-uri 'none'`, `frame-ancestors 'self'`. `connect-src`
  and `frame-src` include the API base and CyberdyneAuth issuer origins so the
  OIDC token/JWKS fetches and silent-renew iframe keep working; the Google Fonts
  origins are allowed for styles/fonts.
- Add response security headers via `src/hooks.server.ts`: `X-Frame-Options:
  DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, and HSTS.

## Impact

- Affected specs: `web-ui` (documentation rendering must sanitize; new
  security-headers requirement).
- Affected code: `mnemosyne-web/src/lib/markdown.ts` (new),
  `src/lib/components/DocumentViewer.svelte`, `svelte.config.js`,
  `src/hooks.server.ts` (new); new `isomorphic-dompurify` dependency; vitest
  regression tests for sanitization and headers.
- Security: closes a token-theft stored-XSS vector and adds clickjacking/HSTS/
  sniffing defences. No behaviour change for legitimate Markdown or the OIDC flow.
