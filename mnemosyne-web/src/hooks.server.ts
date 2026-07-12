import type { Handle } from '@sveltejs/kit';

/**
 * Attach security response headers to every response.
 *
 * The Content-Security-Policy is configured via `kit.csp` in svelte.config.js
 * (it needs SvelteKit's nonce/hash injection). These headers complement it:
 * clickjacking defence, HSTS, referrer minimisation and MIME sniffing defence.
 */
export const securityHeaders: Record<string, string> = {
  'X-Frame-Options': 'DENY',
  'X-Content-Type-Options': 'nosniff',
  'Referrer-Policy': 'strict-origin-when-cross-origin',
  'Strict-Transport-Security': 'max-age=31536000; includeSubDomains'
};

export const handle: Handle = async ({ event, resolve }) => {
  const response = await resolve(event);
  for (const [name, value] of Object.entries(securityHeaders)) {
    response.headers.set(name, value);
  }
  return response;
};
