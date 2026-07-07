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
    // the pilot appears in the leaderboard list with a grade chip
    const row = page.locator('.lrow', { hasText: 'CyberdyneCorp/CyberPythia' });
    await expect(row.first()).toBeVisible();
    await expect(row.first().locator('.gradechip')).toBeVisible();
  });

  test('repository detail shows the health panel', async ({ page }) => {
    await page.goto('/repos/02573958-e1bb-4f6a-adc2-4528bab2ceaf');
    await expect(page.getByRole('heading', { name: 'Health' })).toBeVisible({ timeout: 20_000 });
    // component breakdown renders (documentation is always present once synced)
    await expect(page.getByText('documentation')).toBeVisible();
  });

  test('dashboard shows the PM/PO delivery scorecard', async ({ page }) => {
    await page.goto('/intelligence');
    const scorecard = page.locator('section', {
      has: page.getByRole('heading', { name: 'Delivery scorecard' })
    });
    await expect(scorecard).toBeVisible({ timeout: 20_000 });
    // 238 repos are capped; use the section filter to locate a pilot
    await scorecard.getByPlaceholder('Filter…').fill('CyberdyneAuth');
    const row = scorecard.locator('tr', { hasText: 'CyberdyneCorp/CyberdyneAuth' });
    await expect(row.first()).toBeVisible();
  });

  test('repository detail shows the delivery panel', async ({ page }) => {
    // CyberdyneAuth has issues/PRs -> flow has data
    await page.goto('/repos/9dc307cb-880f-4edb-a0c3-a910cc419036');
    await expect(page.getByRole('heading', { name: 'Delivery' })).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText('Cycle time (issue resolution)')).toBeVisible({ timeout: 20_000 });
  });
});
