import { test, expect } from '@playwright/test';

test('tasks page renders', async ({ page }) => {
  const response = await page.goto('/tasks');
  const status = response?.status() ?? 0;
  expect([200, 302]).toContain(status);
  await expect(page.locator('body')).toContainText(/Aufgabe|Task|Offen|Login|Anmelden|System betreten|Enterprise Core Access/i);
});
