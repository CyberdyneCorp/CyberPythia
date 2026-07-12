import { describe, expect, it } from 'vitest';
import { safeReturnToPath } from './safeRedirect';

describe('safeReturnToPath (open-redirect defence, CWE-601)', () => {
  it('rejects protocol-relative paths that smuggle an off-origin host', () => {
    expect(safeReturnToPath('//evil.com')).toBe('/');
    expect(safeReturnToPath('//evil.com/repos/123')).toBe('/');
  });

  it('rejects absolute off-origin URLs', () => {
    expect(safeReturnToPath('https://evil.com')).toBe('/');
    expect(safeReturnToPath('http://evil.com/steal')).toBe('/');
  });

  it('rejects backslash-prefixed paths browsers may normalise to //', () => {
    expect(safeReturnToPath('/\\evil.com')).toBe('/');
    expect(safeReturnToPath('/\/evil.com')).toBe('/');
  });

  it('rejects non-path and empty values', () => {
    expect(safeReturnToPath(undefined)).toBe('/');
    expect(safeReturnToPath(null)).toBe('/');
    expect(safeReturnToPath('')).toBe('/');
    expect(safeReturnToPath('repos/123')).toBe('/');
  });

  it('preserves ordinary same-origin paths', () => {
    expect(safeReturnToPath('/repos/123')).toBe('/repos/123');
    expect(safeReturnToPath('/')).toBe('/');
    expect(safeReturnToPath('/settings?tab=tokens')).toBe('/settings?tab=tokens');
  });
});
