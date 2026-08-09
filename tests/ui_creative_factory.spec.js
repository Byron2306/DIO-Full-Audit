const { test, expect } = require('@playwright/test');

const url = 'http://127.0.0.1:8765/#market-command';

test('Creative Factory exposes generated families and governed controls', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(url);
  await expect(page.getByRole('heading', { name: 'Creative Factory' })).toBeVisible();
  await expect(page.locator('#creativeFactoryRows tr')).toHaveCount(24);
  await expect(page.locator('#creativeFactoryRows').getByText('Evidex Evidence Pack', { exact: true }).first()).toBeVisible();
  await expect(page.locator('#creativeFactoryRows tr').first()).toContainText('targeted packages');
  await expect(page.locator('#creativeFactoryRows').getByText('ready', { exact: true }).first()).toBeVisible();
  await expect(page.locator('#creativeFactoryRows').getByRole('button', { name: 'Create governed draft' }).first()).toBeEnabled();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBeTruthy();
  await page.screenshot({ path: 'test-results/creative-factory-desktop.png', fullPage: true });
});

test('Creative Factory remains navigable on mobile', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(url);
  await expect(page.getByRole('heading', { name: 'Creative Factory' })).toBeVisible();
  await expect(page.locator('#creativeFactoryRows tr')).toHaveCount(24);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBeTruthy();
  await page.screenshot({ path: 'test-results/creative-factory-mobile.png', fullPage: true });
});
