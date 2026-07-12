import { describe, expect, it, vi } from 'vitest';
import type { RequestEvent } from '@sveltejs/kit';

// The app reads these at runtime via $env/dynamic/public; a NON-localhost value
// proves the CSP is not frozen to the build-time fallback.
vi.mock('$env/dynamic/public', () => ({
  env: {
    PUBLIC_API_BASE_URL: 'https://mnemosyne.backend.example',
    PUBLIC_AUTH_ISSUER: 'https://auth.example.com/realms/mnemosyne'
  }
}));

const { handle, securityHeaders, applyRuntimeCsp, runtimeCspOrigins } = await import(
  './hooks.server'
);

// A minimal stand-in for the CSP header SvelteKit's kit.csp emits, with the
// build-time 'self' placeholders and a script nonce.
const KIT_CSP =
  "default-src 'self'; script-src 'self' 'nonce-abc123'; connect-src 'self'; " +
  "frame-src 'self'; frame-ancestors 'self'; object-src 'none'; base-uri 'none'";

describe('security response headers (CWE-1021)', () => {
  it('sets clickjacking, HSTS, referrer and MIME-sniffing headers on every response', async () => {
    const event = { request: new Request('http://localhost/') } as RequestEvent;
    const resolve = async () => new Response('ok');

    const response = await handle({ event, resolve });

    expect(response.headers.get('X-Frame-Options')).toBe('DENY');
    expect(response.headers.get('X-Content-Type-Options')).toBe('nosniff');
    expect(response.headers.get('Referrer-Policy')).toBe('strict-origin-when-cross-origin');
    expect(response.headers.get('Strict-Transport-Security')).toContain('max-age=');
  });

  it('exposes the full set of security headers', () => {
    expect(Object.keys(securityHeaders)).toEqual(
      expect.arrayContaining([
        'X-Frame-Options',
        'X-Content-Type-Options',
        'Referrer-Policy',
        'Strict-Transport-Security'
      ])
    );
  });
});

describe('runtime Content-Security-Policy connect-src (regression: #58)', () => {
  it('derives connect-src/frame-src from the runtime $env/dynamic/public values', () => {
    const { connectSrc, frameSrc } = runtimeCspOrigins();

    expect(connectSrc).toContain('https://mnemosyne.backend.example');
    expect(connectSrc).toContain('https://auth.example.com');
    expect(frameSrc).toContain('https://auth.example.com');
    // No localhost freeze from the build-time fallback.
    expect(connectSrc.join(' ')).not.toContain('localhost');
  });

  it('rewrites the kit-generated connect-src/frame-src while keeping the script nonce', () => {
    const rewritten = applyRuntimeCsp(KIT_CSP);

    expect(rewritten).toMatch(
      /connect-src 'self' https:\/\/mnemosyne\.backend\.example https:\/\/auth\.example\.com/
    );
    expect(rewritten).toMatch(/frame-src 'self' https:\/\/auth\.example\.com/);
    // The build-time placeholder must not survive as the only connect origin.
    expect(rewritten).not.toMatch(/connect-src 'self';/);
    // Untouched directives (incl. the nonce) are preserved.
    expect(rewritten).toContain("script-src 'self' 'nonce-abc123'");
    expect(rewritten).toContain("object-src 'none'");
    expect(rewritten).toContain("frame-ancestors 'self'");
  });

  it('sets the runtime connect-src on the response CSP header for page responses', async () => {
    const event = { request: new Request('http://localhost/') } as RequestEvent;
    const resolve = async () =>
      new Response('<!doctype html>', {
        headers: { 'content-security-policy': KIT_CSP }
      });

    const response = await handle({ event, resolve });
    const csp = response.headers.get('content-security-policy') ?? '';

    expect(csp).toContain('connect-src');
    expect(csp).toContain('https://mnemosyne.backend.example');
    expect(csp).not.toContain('localhost');
  });

  it('leaves responses without a CSP header (assets, endpoints) untouched', async () => {
    const event = { request: new Request('http://localhost/favicon.svg') } as RequestEvent;
    const resolve = async () => new Response('ok');

    const response = await handle({ event, resolve });

    expect(response.headers.get('content-security-policy')).toBeNull();
  });
});
