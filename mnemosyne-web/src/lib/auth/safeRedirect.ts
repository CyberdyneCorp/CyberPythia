/**
 * Guard the OIDC post-login `returnTo` against open redirect (CWE-601).
 *
 * `returnTo` flows from `page.url.pathname` into the OIDC `state` and back out
 * on the callback. A protocol-relative value like `//evil.com` (or an absolute
 * URL) would otherwise survive as an off-origin redirect. Accept only a
 * single-leading-slash local path that resolves to the same origin; fall back
 * to `/` for anything else.
 */
export function safeReturnToPath(returnTo: string | null | undefined): string {
  if (typeof returnTo !== 'string' || !/^\/(?![/\\])/.test(returnTo)) {
    return '/';
  }
  try {
    const base = 'http://localhost';
    if (new URL(returnTo, base).origin !== base) {
      return '/';
    }
  } catch {
    return '/';
  }
  return returnTo;
}
