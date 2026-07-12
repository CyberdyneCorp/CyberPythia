import adapter from '@sveltejs/adapter-node';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

// Origins the app must reach at runtime. Mirrors the defaults in
// src/lib/config.ts so the Content-Security-Policy allows the API and the
// CyberdyneAuth issuer (token/JWKS/discovery fetches + the silent-renew iframe).
function originOf(url, fallback) {
  try {
    return new URL(url ?? fallback).origin;
  } catch {
    return new URL(fallback).origin;
  }
}

const apiOrigin = originOf(process.env.PUBLIC_API_BASE_URL, 'http://localhost:8000');
const authOrigin = originOf(
  process.env.PUBLIC_AUTH_ISSUER,
  'https://auth.backend.coolify.cyberdynecorp.ai'
);

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter(),
    csp: {
      // 'auto' emits nonces for dynamically-rendered pages and hashes for
      // prerendered ones, so SvelteKit's own inline scripts/styles (and the
      // theme bootstrap script in app.html) stay allowed WITHOUT 'unsafe-inline'
      // on script-src.
      mode: 'auto',
      directives: {
        'default-src': ['self'],
        'script-src': ['self'],
        // Inline <style> blocks (Svelte scoped styles) are covered by the
        // SvelteKit nonce/hash; the Google Fonts stylesheet needs its host.
        'style-src': ['self', 'unsafe-inline', 'https://fonts.googleapis.com'],
        // Inline style="" attributes (e.g. app.html) — nonces cannot cover
        // attributes, so allow them explicitly here.
        'style-src-attr': ['unsafe-inline'],
        'font-src': ['self', 'https://fonts.gstatic.com'],
        'img-src': ['self', 'data:', 'https:'],
        'connect-src': ['self', apiOrigin, authOrigin],
        // oidc-client-ts silent renew loads the authorize endpoint in a hidden iframe.
        'frame-src': ['self', authOrigin],
        'object-src': ['none'],
        'base-uri': ['none'],
        'frame-ancestors': ['self'],
        'form-action': ['self']
      }
    }
  }
};

export default config;
