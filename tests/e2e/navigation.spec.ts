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
    '/settings'
  ];

  const readyStateByRoute: Record<string, string> = {
    '/dashboard': 'dashboard-ready',
    '/upload': 'upload-ready',
    '/projects': 'projects-ready',
    '/tasks': 'tasks-ready',
    '/messenger': 'messenger-ready',
    '/email': 'email-ready',
    '/calendar': 'calendar-ready',
    '/time': 'time-ready',
    '/visualizer': 'visualizer-ready',
    '/settings': 'settings-ready',
  };

  test('main navigation flow with dev login and full-page checks', async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[name="username"]', 'dev');
    await page.fill('input[name="password"]', 'dev');
    await page.click('button[type="submit"]');

    await expect(page).toHaveURL(/dashboard|\/$/);

    for (const route of routes) {
      await page.click(`a[href="${route}"]`);
      await expect(page).toHaveURL(new RegExp(`${route.replace('/', '\\/')}$`));
      await expect(page.locator('body')).not.toContainText(/wird geladen/i);
      const ready = readyStateByRoute[route];
      if (ready) await expect(page.locator(`[data-ready-state="${ready}"]`)).toBeVisible();
      await expect(page.locator('#main-content')).toBeVisible();
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
      await expect(page.locator('body')).toContainText(/KUKANILEA|Dashboard|Upload|Projekt|Aufgabe|Kalender|Einstellungen|Login|Anmelden/i);
      await expect(page.locator('body')).not.toContainText(/wird geladen/i);
      const ready = readyStateByRoute[route];
      if (ready) await expect(page.locator(`[data-ready-state="${ready}"]`)).toBeVisible();
    });
  }
});
