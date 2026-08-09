const { test, expect } = require('@playwright/test');

const url = 'http://127.0.0.1:8765/';

test('Approved Lingua flags remain inspectable in the semantic workspace', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(url);
  await page.getByRole('button', { name: 'Lingua QA' }).first().click();
  await page.getByRole('button', { name: 'Inspect approval' }).first().click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  await expect(dialog.getByLabel('Reviewer name')).toBeVisible();
  await expect(dialog.getByText('Meaning approved').first()).toBeVisible();
  await expect(dialog.getByRole('button', { name: 'Already crystallized' })).toBeVisible();
  await page.screenshot({ path: 'test-results/lingua-review-desktop.png', fullPage: true });
});

test('Lingua approval receipt remains inspectable on a mobile viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(url);
  await page.getByRole('button', { name: 'Lingua QA' }).first().click();
  await page.getByRole('button', { name: 'Inspect approval' }).first().click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole('button', { name: 'Already crystallized' })).toBeVisible();
  await page.screenshot({ path: 'test-results/lingua-review-mobile.png', fullPage: true });
});

for (const product of ['homs', 'sophia', 'evidex', 'vamp']) {
  test(`${product} intake carries the shared Lingua language request`, async ({ page }) => {
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(`${url}sites/${product}/`);
    const language = page.locator('select[name="output_language"]');
    await expect(language).toBeVisible();
    await expect(language.locator('option')).toHaveCount(5);
    await language.selectOption({ label: 'Setswana' });
    await expect(language).toHaveValue('Setswana');
    expect(errors).toEqual([]);
  });
}
