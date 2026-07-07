import { defineConfig } from '@playwright/test';

/**
 * E2E tests against a deployed Mnemosyne (staging/production).
 *
 * Required env:
 *   E2E_WEB_URL      (default https://mnemosyne.coolify.cyberdynecorp.ai)
 *   E2E_API_URL      (default https://mnemosyne.backend.coolify.cyberdynecorp.ai)
 *   E2E_AUTH_URL     (default https://auth.backend.coolify.cyberdynecorp.ai)
 *   E2E_USER_EMAIL / E2E_USER_PASSWORD   test user (admin + mnemosyne entitlement)
 *
 * Run: npm run test:e2e
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  retries: 1,
  workers: 1, // shared backend state; keep deterministic
  use: {
    baseURL: process.env.E2E_WEB_URL ?? 'https://mnemosyne.coolify.cyberdynecorp.ai',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure'
  },
  reporter: [['list']]
});
