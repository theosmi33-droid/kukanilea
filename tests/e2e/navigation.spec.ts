import { test, expect } from '@playwright/test';

test.describe('Sovereign navigation', () => {
  const routes = [
    '/dashboard',
    '/upload',
    '/projects',
    '/tasks',
    '/messenger',
    '/email',
    '/calendar',
    '/time',
    '/visualizer',
    '/settings',
    '/assistant'
  ];

  test('main navigation flow with dev login and full-page checks', async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[name="username"]', 'dev');
    await page.fill('input[name="password"]', 'dev');
    await page.click('button[type="submit"]');

    await expect(page).toHaveURL(/dashboard|\/$/);

    for (const route of routes) {
      await page.click(`a[href="${route}"]`);
      await expect(page).toHaveURL(new RegExp(`${route.replace('/', '\\/')}$`));
      await expect(page.locator('body')).not.toContainText(/wird geladen|Lade Quellen/i);
      await expect(page.locator('#main-content[data-page-ready="1"]')).toBeVisible();
      if (route === '/upload') {
        await expect(page.locator('input[name="file"]')).toBeVisible();
      }
    }
  });

  for (const route of routes) {
    test(`route responds and renders ${route}`, async ({ page }) => {
      const response = await page.goto(route);
      const status = response?.status() ?? 0;
      expect([200, 302]).toContain(status);
      await expect(page.locator('body')).toContainText(/KUKANILEA|Dashboard|Upload|Projekt|Aufgabe|Kalender|Einstellungen|Assistant|Login|Anmelden/i);
      await expect(page.locator('body')).not.toContainText(/wird geladen|Lade Quellen/i);
    });
  }
});
