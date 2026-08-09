const { test, expect } = require('@playwright/test');

const url = 'http://127.0.0.1:8765/';

test('Commercial Triune exposes the canonical transaction and reconciles internally', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(url);
  await page.getByRole('button', { name: 'Transactions' }).first().click();
  await expect(page.getByRole('heading', { name: 'Commercial Transaction Spine' })).toBeVisible();
  await expect(page.locator('#transactionRows').getByText('TXN-0B5E995B52C900E0', { exact: true })).toBeVisible();
  await expect(page.locator('#transactionRows').getByText('collect or validate intake', { exact: true })).toBeVisible();

  page.once('dialog', dialog => dialog.accept());
  const response = page.waitForResponse(result => result.url().endsWith('/api/control/transaction/action'));
  await page.getByRole('button', { name: 'Reconcile now' }).click();
  expect((await response).ok()).toBeTruthy();
  await expect(page.locator('#toast')).toContainText('commercial transaction(s) reconciled');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBeTruthy();
  await page.screenshot({ path: 'test-results/commercial-triune-desktop.png', fullPage: true });
});

test('Commercial transaction spine remains navigable on mobile', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(url);
  await page.getByRole('button', { name: 'Transactions' }).first().click();
  await expect(page.getByRole('heading', { name: 'Commercial Transaction Spine' })).toBeVisible();
  await expect(page.locator('#transactionRows').getByText('TXN-0B5E995B52C900E0', { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBeTruthy();
  await page.screenshot({ path: 'test-results/commercial-triune-mobile.png', fullPage: true });
});
