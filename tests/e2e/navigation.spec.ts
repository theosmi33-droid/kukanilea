import fs from 'fs';
import { test, expect, chromium } from '@playwright/test';

test.describe('Sovereign navigation', () => {
  test.beforeEach(async () => {
    test.skip(!fs.existsSync(chromium.executablePath()), 'Playwright browser executable unavailable in this environment');
  });
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
    await expect(page.locator('#main-content')).toBeVisible();

    for (const route of routes) {
      await page.locator(`a[href="${route}"]`).first().click();
      await expect(page).toHaveURL(new RegExp(`${route.replace('/', '\\/')}$`));
      await expect(page.locator('#main-content')).toBeVisible();
      await expect(page.locator('body')).not.toContainText(/wird geladen/i);
    }
  });

  for (const route of routes) {
    test(`route responds and renders ${route}`, async ({ page }) => {
      const response = await page.goto(route);
      const status = response?.status() ?? 0;
      expect([200, 302]).toContain(status);
      await expect(page.locator('body')).toContainText(/KUKANILEA|Dashboard|Upload|Projekt|Aufgabe|Kalender|Einstellungen|Assistant|Login|Anmelden/i);
      await expect(page.locator('body')).not.toContainText(/wird geladen/i);
    });
  }
});
