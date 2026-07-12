# Tasks

## 1. Markdown sanitization (#55)
- [x] 1.1 Add `isomorphic-dompurify` dependency
- [x] 1.2 Add `src/lib/markdown.ts` `renderMarkdown()` that parses with `marked` then sanitizes with DOMPurify
- [x] 1.3 Consume `renderMarkdown()` in `DocumentViewer.svelte`; remove the "trusted internal markdown" comment
- [x] 1.4 Add `src/lib/markdown.test.ts` asserting `<script>`, `onerror`, and `javascript:` payloads are stripped and safe formatting survives

## 2. CSP + security headers (#58)
- [x] 2.1 Configure `kit.csp` (mode `auto`) in `svelte.config.js` with strict directives; include API + auth origins in connect-src/frame-src and Google Fonts origins
- [x] 2.2 Add `src/hooks.server.ts` setting X-Frame-Options, X-Content-Type-Options, Referrer-Policy, HSTS on every response
- [x] 2.3 Add `src/hooks.server.test.ts` asserting the security headers are set

## 3. Verify
- [x] 3.1 `npm run test`, `npm run check`, `npm run build` pass
- [x] 3.2 Confirm the served CSP + security headers on a running build and that nonces are injected
