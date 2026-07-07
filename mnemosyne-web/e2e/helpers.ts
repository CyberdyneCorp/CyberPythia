import { expect, type APIRequestContext, type Page } from '@playwright/test';

export const WEB_URL = process.env.E2E_WEB_URL ?? 'https://mnemosyne.coolify.cyberdynecorp.ai';
export const API_URL =
  process.env.E2E_API_URL ?? 'https://mnemosyne.backend.coolify.cyberdynecorp.ai';
export const AUTH_URL =
  process.env.E2E_AUTH_URL ?? 'https://auth.backend.coolify.cyberdynecorp.ai';
export const USER_EMAIL = process.env.E2E_USER_EMAIL ?? '';
export const USER_PASSWORD = process.env.E2E_USER_PASSWORD ?? '';

export function requireCredentials(): void {
  if (!USER_EMAIL || !USER_PASSWORD) {
    throw new Error('E2E_USER_EMAIL / E2E_USER_PASSWORD must be set');
  }
}

/** Password login against CyberdyneAuth; returns a bearer token for API tests. */
export async function apiToken(request: APIRequestContext): Promise<string> {
  requireCredentials();
  const response = await request.post(`${AUTH_URL}/api/v1/auth/login`, {
    data: { email: USER_EMAIL, password: USER_PASSWORD }
  });
  expect(response.ok(), `login failed: ${response.status()}`).toBeTruthy();
  return (await response.json()).access_token;
}

/**
 * Drive the full "Connect with Cyberdyne" browser flow:
 * dashboard -> OIDC authorize -> hosted login page -> callback -> dashboard.
 */
export async function signInThroughBrowser(page: Page): Promise<void> {
  requireCredentials();
  await page.goto('/');
  await page.getByRole('button', { name: 'Connect with Cyberdyne' }).click();

  // authorize redirects anonymous users to the hosted login page (?next=…)
  await page.waitForURL(/login/, { timeout: 20_000 });
  await page.locator('input[type="email"], input[name="email"]').first().fill(USER_EMAIL);
  await page.locator('input[type="password"]').first().fill(USER_PASSWORD);
  await page.locator('button[type="submit"]').first().click();

  // back on the app once the callback code exchange finishes
  await page.waitForURL(new RegExp(new URL(WEB_URL).host), { timeout: 30_000 });
  await expect(page.getByRole('button', { name: 'Sign out' })).toBeVisible({ timeout: 30_000 });
}
