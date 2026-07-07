import { expect, test } from '@playwright/test';

/** Requires at least one synced repository (pilot: CyberdyneCorp/CyberdyneAuth). */
test.use({ storageState: 'e2e/.auth/user.json' });

test.describe('populated dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('button', { name: 'Sign out' })).toBeVisible({ timeout: 20_000 });
  });

  test('repository cards show synced pilots', async ({ page }) => {
    await expect(page.getByText('CyberdyneCorp/CyberdyneAuth')).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText('CyberdyneCorp/CyberPythia')).toBeVisible();
    const card = page.locator('.repo', { hasText: 'CyberdyneCorp/CyberdyneAuth' });
    await expect(card.getByText(/synced/)).toBeVisible();
  });

  test('repository detail: overview, documentation, and metrics render real data', async ({
    page
  }) => {
    await page.getByRole('link', { name: 'CyberdyneCorp/CyberdyneAuth' }).click();
    await expect(page.getByRole('heading', { name: 'CyberdyneCorp/CyberdyneAuth' })).toBeVisible({
      timeout: 20_000
    });
    // Overview stats
    await expect(page.getByText('docs', { exact: true })).toBeVisible();

    // Documentation tab lists captured docs and renders content
    await page.getByRole('button', { name: 'Documentation', exact: true }).click();
    const docLink = page.getByRole('button', { name: 'docs/two-factor-auth.md' });
    await expect(docLink).toBeVisible({ timeout: 15_000 });
    await docLink.click();
    await expect(page.getByText(/two-factor|TOTP|authenticator/i).first()).toBeVisible();

    // OpenSpec tab shows captured changes
    await page.getByRole('button', { name: 'OpenSpec', exact: true }).click();
    await expect(page.locator('details.card').first()).toBeVisible({ timeout: 15_000 });

    // Issues tab renders the table
    await page.getByRole('button', { name: 'Issues', exact: true }).click();
    await expect(page.locator('table tbody tr').first()).toBeVisible({ timeout: 15_000 });

    // Metrics tab renders stat cards
    await page.getByRole('button', { name: 'Metrics', exact: true }).click();
    await expect(page.getByText('merge rate')).toBeVisible({ timeout: 15_000 });
  });

  test('agent context tab answers a question with citations', async ({ page }) => {
    test.setTimeout(150_000); // LLM answer synthesis can take a while
    await page.getByRole('link', { name: 'CyberdyneCorp/CyberdyneAuth' }).click();
    await page.getByRole('button', { name: 'Agent Context', exact: true }).click();
    await page
      .getByPlaceholder(/How is authentication implemented/)
      .fill('How does two-factor authentication work?');
    await page.getByRole('button', { name: 'Go' }).click();
    await expect(page.getByRole('heading', { name: 'Sources' })).toBeVisible({ timeout: 60_000 });
  });
});
