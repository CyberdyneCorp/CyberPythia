import { expect, test } from '@playwright/test';
import { AUTH_URL, WEB_URL, signInThroughBrowser } from './helpers';

test.describe('web login (Connect with Cyberdyne)', () => {
  test('landing page shows the sign-in gate', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('button', { name: 'Connect with Cyberdyne' })).toBeVisible();
  });

  test('OIDC discovery is reachable from the web origin (CORS)', async ({ page }) => {
    // Regression: missing CORS_ALLOWED_ORIGINS entry made the button do nothing.
    await page.goto('/');
    const result = await page.evaluate(async (authUrl) => {
      try {
        const response = await fetch(`${authUrl}/.well-known/openid-configuration`);
        return { ok: response.ok, status: response.status };
      } catch (error) {
        return { ok: false, error: String(error) };
      }
    }, AUTH_URL);
    expect(result.ok, `discovery fetch blocked: ${JSON.stringify(result)}`).toBeTruthy();
  });

  test('clicking Connect with Cyberdyne redirects to the login page', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'Connect with Cyberdyne' }).click();
    await page.waitForURL(/login|authorize/, { timeout: 20_000 });
    expect(page.url()).not.toBe(`${WEB_URL}/`); // must have navigated away
  });

  test('full login round-trip establishes a session', async ({ page }) => {
    await signInThroughBrowser(page);
    // Entitled user lands on the repositories dashboard
    await expect(page.getByRole('heading', { name: 'Repositories' })).toBeVisible({
      timeout: 20_000
    });
  });
});
