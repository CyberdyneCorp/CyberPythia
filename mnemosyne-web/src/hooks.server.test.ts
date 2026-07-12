import { describe, expect, it } from 'vitest';
import type { RequestEvent } from '@sveltejs/kit';
import { handle, securityHeaders } from './hooks.server';

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
