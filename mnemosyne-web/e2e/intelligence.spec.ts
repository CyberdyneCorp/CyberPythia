import { expect, test } from '@playwright/test';

/** Phase 5 intelligence dashboard + repository health panel. */
test.use({ storageState: 'e2e/.auth/user.json' });

test.describe('engineering intelligence', () => {
  test('portfolio dashboard shows the health leaderboard', async ({ page }) => {
    await page.goto('/intelligence');
    await expect(page.getByRole('heading', { name: 'Engineering Intelligence' })).toBeVisible({
      timeout: 20_000
    });
    await expect(page.getByRole('heading', { name: 'Health leaderboard' })).toBeVisible({
      timeout: 20_000
    });
    // both indexed pilots appear in the leaderboard with a grade badge
    const row = page.locator('tr', { hasText: 'CyberdyneCorp/CyberPythia' });
    await expect(row).toBeVisible();
    await expect(row.locator('.badge')).toBeVisible();
  });

  test('repository detail shows the health panel', async ({ page }) => {
    await page.goto('/repos/02573958-e1bb-4f6a-adc2-4528bab2ceaf');
    await expect(page.getByRole('heading', { name: 'Health' })).toBeVisible({ timeout: 20_000 });
    // component breakdown renders (documentation is always present once synced)
    await expect(page.getByText('documentation')).toBeVisible();
  });

  test('dashboard shows the PM/PO delivery scorecard', async ({ page }) => {
    await page.goto('/intelligence');
    await expect(page.getByRole('heading', { name: 'Delivery scorecard' })).toBeVisible({
      timeout: 20_000
    });
    const row = page.locator('tr', { hasText: 'CyberdyneCorp/CyberdyneAuth' });
    await expect(row.first()).toBeVisible();
  });

  test('repository detail shows the delivery panel', async ({ page }) => {
    // CyberdyneAuth has issues/PRs -> flow has data
    await page.goto('/repos/9dc307cb-880f-4edb-a0c3-a910cc419036');
    await expect(page.getByRole('heading', { name: 'Delivery' })).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText('Cycle time (issue resolution)')).toBeVisible({ timeout: 20_000 });
  });
});
