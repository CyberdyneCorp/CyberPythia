import type { Handle } from '@sveltejs/kit';
import { env } from '$env/dynamic/public';

/**
 * Attach security response headers to every response.
 *
 * SvelteKit's `kit.csp` (svelte.config.js) owns the nonce/hash plumbing for
 * inline scripts/styles and emits the Content-Security-Policy header. It cannot,
 * however, know the API/auth origins the app talks to: those are read at RUNTIME
 * from `$env/dynamic/public` (src/lib/config.ts) and are unknown at build time.
 * So here we rewrite the `connect-src`/`frame-src` directives of that header from
 * the SAME runtime env, keeping a single authoritative CSP whose `connect-src`
 * always matches what src/lib/api/http.ts actually fetches.
 *
 * The remaining headers complement it: clickjacking defence, HSTS, referrer
 * minimisation and MIME sniffing defence.
 */
export const securityHeaders: Record<string, string> = {
  'X-Frame-Options': 'DENY',
  'X-Content-Type-Options': 'nosniff',
  'Referrer-Policy': 'strict-origin-when-cross-origin',
  'Strict-Transport-Security': 'max-age=31536000; includeSubDomains'
};

// Fallbacks mirror src/lib/config.ts so the CSP matches the app's own defaults.
const API_FALLBACK = 'http://localhost:8000';
const AUTH_FALLBACK = 'https://auth.backend.coolify.cyberdynecorp.ai';

function originOf(url: string | undefined, fallback: string): string {
  try {
    return new URL(url ?? fallback).origin;
  } catch {
    return new URL(fallback).origin;
  }
}

/**
 * Runtime CSP source lists, derived from the same dynamic public env the app
 * reads. `connect-src` covers the API + auth (token/JWKS/discovery fetches);
 * `frame-src` covers the auth origin for oidc-client-ts' silent-renew iframe.
 */
export function runtimeCspOrigins(): { connectSrc: string[]; frameSrc: string[] } {
  const apiOrigin = originOf(env.PUBLIC_API_BASE_URL, API_FALLBACK);
  const authOrigin = originOf(env.PUBLIC_AUTH_ISSUER, AUTH_FALLBACK);
  return {
    connectSrc: [...new Set(["'self'", apiOrigin, authOrigin])],
    frameSrc: [...new Set(["'self'", authOrigin])]
  };
}

/**
 * Rewrite `connect-src`/`frame-src` in a SvelteKit-generated CSP header with the
 * runtime origins, leaving every other directive (including the script nonce)
 * untouched, so the emitted header is never frozen to the build-time fallback.
 */
export function applyRuntimeCsp(csp: string): string {
  const { connectSrc, frameSrc } = runtimeCspOrigins();
  const setDirective = (header: string, name: string, values: string[]): string => {
    const directive = `${name} ${values.join(' ')}`;
    const pattern = new RegExp(`\\b${name}\\b[^;]*`);
    return pattern.test(header) ? header.replace(pattern, directive) : `${header}; ${directive}`;
  };
  return setDirective(setDirective(csp, 'connect-src', connectSrc), 'frame-src', frameSrc);
}

export const handle: Handle = async ({ event, resolve }) => {
  const response = await resolve(event);
  for (const [name, value] of Object.entries(securityHeaders)) {
    response.headers.set(name, value);
  }
  const csp = response.headers.get('content-security-policy');
  if (csp) {
    response.headers.set('content-security-policy', applyRuntimeCsp(csp));
  }
  return response;
};
