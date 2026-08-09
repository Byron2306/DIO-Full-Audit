const { test, expect } = require('@playwright/test');

const controlDeck = 'http://127.0.0.1:8765/';
const marketCommand = 'http://127.0.0.1:8770/';

test('Market Command is a native dark Control Deck workspace', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(controlDeck);
  await page.getByRole('button', { name: 'Market Command' }).first().click();
  await expect(page.getByRole('heading', { name: 'Channel Adapters' })).toBeVisible();
  await expect(page.getByText('YOUTUBE_ORGANIC', { exact: true })).toBeVisible();
  await expect(page.locator('#marketCommandRows').getByText('CMP-D3E55414C7B5', { exact: true })).toBeVisible();
  const background = await page.locator('body').evaluate(node => getComputedStyle(node).backgroundColor);
  expect(background).toBe('rgb(9, 13, 15)');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBeTruthy();
  await page.screenshot({ path: 'test-results/market-command-control-deck.png', fullPage: true });
});

test('Market Command remains usable on mobile', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(controlDeck);
  await page.getByRole('button', { name: 'Market Command' }).first().click();
  await expect(page.getByRole('heading', { name: 'Channel Adapters' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBeTruthy();
  await page.screenshot({ path: 'test-results/market-command-mobile.png', fullPage: true });
});

test('Expanded Market Command exposes adapters and governed experiments', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(marketCommand);
  await expect(page.getByRole('heading', { name: 'Market Command.' })).toBeVisible();
  await expect(page.locator('#channelsGrid').getByText('YouTube', { exact: true })).toBeVisible();
  await expect(page.getByText('HOMS Assessment Desk proof experiment', { exact: true })).toBeVisible();
  await expect(page.getByText('Automatic Spend')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Agency Procurement' })).toBeVisible();
  const adclick = page.locator('#agencyGrid tr').filter({ hasText: 'Adclick Africa' });
  await expect(adclick.getByText('96/100', { exact: true })).toBeVisible();
  await adclick.getByRole('button', { name: 'prepare RFQ' }).click();
  await expect(page.getByRole('heading', { name: 'Prepare agency RFQ' })).toBeVisible();
});
