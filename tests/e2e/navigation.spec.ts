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
