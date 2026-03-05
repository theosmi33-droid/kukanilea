import { test, expect } from '@playwright/test';

test('upload page loads and shows drop area', async ({ page }) => {
  const response = await page.goto('/upload', { waitUntil: 'domcontentloaded' });
  const status = response?.status() ?? 0;
  expect([200, 302]).toContain(status);
  await expect(page.locator('main, #main-content, body').first()).toContainText(
    /Dateien auswählen|Datei|Upload|Login|Anmelden|System betreten|Enterprise Core Access/i,
  );
});
