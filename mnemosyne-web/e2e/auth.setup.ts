import { test as setup } from '@playwright/test';
import { signInThroughBrowser } from './helpers';

setup('authenticate', async ({ page }) => {
  await signInThroughBrowser(page);
  await page.context().storageState({ path: 'e2e/.auth/user.json' });
});
