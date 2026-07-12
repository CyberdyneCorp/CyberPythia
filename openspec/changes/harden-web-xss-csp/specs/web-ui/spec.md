# web-ui Specification

## ADDED Requirements

### Requirement: Sanitized Markdown rendering

The UI SHALL sanitize all GitHub-derived Markdown before injecting it as HTML into the DOM, and SHALL NOT inject unsanitized `marked` output via `{@html}`. Sanitized output SHALL strip active content — `<script>` elements, event-handler attributes (e.g. `onerror`), and `javascript:` URL schemes — while preserving safe formatting (headings, emphasis, links, code, images).

#### Scenario: Malicious document content is neutralized
- **WHEN** a captured document contains `<img src=x onerror="...">`, a
  `<script>` tag, or a `[label](javascript:...)` link
- **THEN** the rendered output SHALL contain none of the event handler, script
  element, or `javascript:` scheme, so no attacker script executes in the
  operator's session

#### Scenario: Safe formatting is preserved
- **WHEN** a document contains normal Markdown (headings, bold, links)
- **THEN** the rendered output SHALL retain that formatting

### Requirement: HTTP security headers

Every response from the web application SHALL carry a Content-Security-Policy, `X-Frame-Options`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, and `Strict-Transport-Security`. The Content-Security-Policy SHALL set `default-src 'self'`, `object-src 'none'`, `base-uri 'none'`, `frame-ancestors 'self'`, and a `script-src` that does NOT allow `'unsafe-inline'` (inline scripts allowed only via per-response nonce/hash). The policy SHALL permit the configured API base origin and CyberdyneAuth issuer origin in `connect-src`/`frame-src` so the OIDC sign-in, token exchange, and silent renew continue to work.

#### Scenario: Response carries a strict CSP and hardening headers
- **WHEN** the browser requests any page of the web app
- **THEN** the response SHALL include a Content-Security-Policy with
  `default-src 'self'` and a nonce-based `script-src` without `'unsafe-inline'`,
  plus `X-Frame-Options`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`,
  and `Strict-Transport-Security`

#### Scenario: OIDC flow is not broken by CSP
- **WHEN** the app performs the CyberdyneAuth token exchange and silent renew
- **THEN** the CSP `connect-src`/`frame-src` SHALL allow the auth issuer origin
  so authentication succeeds
