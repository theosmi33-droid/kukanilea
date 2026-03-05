import { test, expect } from '@playwright/test';
import { loginAsDev, navigateViaSidebar, waitForShellReady } from './support/uiStability';

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
    '/assistant',
  ];

  test('main navigation flow with dev login and full-page checks', async ({ page }) => {
    await loginAsDev(page);

    for (const route of routes) {
      await navigateViaSidebar(page, route);
      if (route === '/upload') {
        await expect(page.locator('input[name="file"]')).toBeVisible();
      }
    }
  });

  test('visual smoke snapshots for primary routes', async ({ page }) => {
    await loginAsDev(page);

    for (const route of routes.slice(0, 10)) {
      await page.goto(route, { waitUntil: 'domcontentloaded' });
      await waitForShellReady(page);
      await expect(page.locator('#main-content')).toHaveScreenshot(`nav-smoke-${route.replace('/', '')}.png`, {
        animations: 'disabled',
        maxDiffPixelRatio: 0.05,
      });
    }
  });

  for (const route of routes) {
    test(`route responds and renders ${route}`, async ({ page }) => {
      const response = await page.goto(route, { waitUntil: 'domcontentloaded' });
      const status = response?.status() ?? 0;
      expect([200, 302]).toContain(status);
      await expect(page.locator('body')).toContainText(
        /KUKANILEA|Dashboard|Upload|Projekt|Aufgabe|Kalender|Einstellungen|Assistant|Login|Anmelden/i,
      );
      await expect(page.locator('body')).not.toContainText(/wird geladen|Lade Quellen/i);
    });
  }
});
