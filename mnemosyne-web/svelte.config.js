import adapter from '@sveltejs/adapter-node';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

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
        // The API and CyberdyneAuth origins are only known at RUNTIME (they come
        // from $env/dynamic/public, like src/lib/config.ts). src/hooks.server.ts
        // rewrites these two directives per-request from that same env; the
        // 'self' placeholders here just keep the directives present in the
        // SvelteKit-generated header so the runtime rewrite has something to fill.
        'connect-src': ['self'],
        // oidc-client-ts silent renew loads the authorize endpoint in a hidden iframe.
        'frame-src': ['self'],
        'object-src': ['none'],
        'base-uri': ['none'],
        'frame-ancestors': ['self'],
        'form-action': ['self']
      }
    }
  }
};

export default config;
